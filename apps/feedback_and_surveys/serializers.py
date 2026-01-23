from rest_framework import serializers
from .models import Survey, SurveyQuestion, SurveySubmission, QuestionAnswer, SubmissionAttachment, SubmissionActivityLog,AutomationRule
from apps.audience_manager.models import AudienceContact

class SurveyQuestionSerializer(serializers.ModelSerializer):
    """
    Serializer for a single element on the canvas.
    """
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SurveyQuestion
        fields = ['id', 'type', 'label', 'order', 'is_required', 'properties']

class SurveySerializer(serializers.ModelSerializer):
    """
    Main Serializer for the Survey Builder.
    """
    questions = SurveyQuestionSerializer(many=True, required=False)
    audience_name = serializers.CharField(source='audience.name', read_only=True)
    class Meta:
        model = Survey
        fields = [
            'id', 'title', 'description', 
            'status', 'is_active', 
            'theme', 'language', 
            'questions','audience', 'audience_name',
            'created_at', 'target_audience_count'
        ]

    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])     
        survey = Survey.objects.create(**validated_data)
        for q_data in questions_data:
            SurveyQuestion.objects.create(survey=survey, **q_data)
        return survey

    def update(self, instance, validated_data):
        questions_data = validated_data.pop('questions', None)
        
        # 1. Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 2. Update Questions (Delete old -> Create new)
        if questions_data is not None:
            instance.questions.all().delete()
            for q_data in questions_data:
                q_data.pop('id', None) 
                SurveyQuestion.objects.create(survey=instance, **q_data)

        return instance

class QuestionAnswerSerializer(serializers.ModelSerializer):
    question_label = serializers.CharField(source='question.label', read_only=True)
    
    class Meta:
        model = QuestionAnswer
        fields = ['id', 'question', 'question_label', 'answer_value']

class SubmissionAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionAttachment
        fields = ['id', 'file', 'file_name', 'file_size']

class SubmissionActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    class Meta:
        model = SubmissionActivityLog
        fields = ['id', 'actor_name', 'action', 'created_at']

class SurveySubmissionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True, default="Anonymous")
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    customer_location = serializers.SerializerMethodField()
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    answers = QuestionAnswerSerializer(many=True, read_only=True)
    category = serializers.CharField(source='get_category_display',read_only=True)
    attachments = SubmissionAttachmentSerializer(many=True, read_only=True)
    activity_logs = SubmissionActivityLogSerializer(many=True, read_only=True)

    class Meta:
        model = SurveySubmission
        fields = [
            'id', 'survey', 'survey_title', 
            'customer_name', 'customer_email', 'customer_location',
            'rating', 'comment', 'status', 'priority', 'is_flagged', 
            'category','channel', 'assigned_to', 'created_at', 
            'answers', 'attachments', 'activity_logs'
        ]

    def get_customer_location(self, obj):
        if obj.customer:
            return f"{obj.customer.city}, {obj.customer.country}" if hasattr(obj.customer, 'city') else "Unknown"
        return "Unknown"
class SurveyCampaignSerializer(serializers.ModelSerializer):
    response_count = serializers.IntegerField(source='submissions.count', read_only=True)
    completion_rate = serializers.SerializerMethodField()
    audience_name = serializers.CharField(source='audience.name', read_only=True)
    class Meta:
        model = Survey
        fields = ['id', 'title', 'status', 'created_at', 'audience_name','target_audience_count', 'response_count', 'completion_rate','survey_type']
    def get_completion_rate(self, obj):
        if obj.target_audience_count > 0:
            return round((obj.submissions.count() / obj.target_audience_count) * 100, 1)
        return 0.0

class DashboardFeedbackTableSerializer(serializers.ModelSerializer):
    customer = serializers.CharField(source='customer.name', read_only=True, default="Anonymous")
    message = serializers.CharField(source='comment', read_only=True)
    category = serializers.CharField(source='get_category_display',read_only=True)
    class Meta:
        model = SurveySubmission
        fields = ['id', 'customer', 'rating', 'category', 'message', 'status']

class InboxSubmissionSerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %I:%M %p")    
    customer = serializers.SerializerMethodField()
    rating = serializers.IntegerField()    
    feedback_snippet = serializers.SerializerMethodField()
    channel = serializers.CharField()
    category = serializers.CharField(source='get_category_display',read_only=True) 
    status = serializers.CharField()
    assigned_to = serializers.SerializerMethodField()

    class Meta:
        model = SurveySubmission
        fields = [
            'id', 
            'date', 
            'customer', 
            'rating', 
            'feedback_snippet', 
            'channel', 
            'category', 
            'status', 
            'assigned_to'
        ]

    def get_customer(self, obj):
        name = "Anonymous"
        email = ""
        initial = "?"
        if obj.customer:
            name = obj.customer.name if obj.customer.name else "Anonymous"
            email = obj.customer.email if obj.customer.email else ""
        if name and name != "Anonymous":
            initial = name[0].upper()
        
        return {
            "name": name,
            "email": email,
            "initial": initial
        }
    def get_feedback_snippet(self, obj):
        return {
            "comment": obj.comment,
            "is_flagged": obj.is_flagged,
            "has_attachments": obj.attachments.exists() 
        }

    def get_assigned_to(self, obj):
        return obj.assigned_to.get_full_name() if obj.assigned_to else "Unassigned"
class FeedbackDetailSerializer(serializers.ModelSerializer):
    # 1. Customer Profile Section
    customer_profile = serializers.SerializerMethodField()
    
    # 2. Feedback Content Section
    feedback_content = serializers.SerializerMethodField()
    
    # 3. Action Logs Section
    action_logs = serializers.SerializerMethodField()

    class Meta:
        model = SurveySubmission
        fields = ['id', 'customer_profile', 'feedback_content', 'action_logs']

    def get_customer_profile(self, obj):
        # Defaults
        name = "Anonymous"
        email = "N/A"
        phone = "N/A"
        location = "Unknown"
        initial = "?"

        if obj.customer:
            name = obj.customer.name or "Anonymous"
            email = obj.customer.email or "N/A"
            phone = getattr(obj.customer, 'phone', "N/A") # Check if phone exists
            # Assuming your customer model has city/country fields
            city = getattr(obj.customer, 'city', "")
            country = getattr(obj.customer, 'country', "")
            location = f"{city}, {country}".strip(', ') or "Unknown"

        if name != "Anonymous":
            initial = name[0].upper()

        return {
            "name": name,
            "email": email,
            "phone": phone,
            "location": location,
            "initial": initial
        }

    def get_feedback_content(self, obj):
        return {
            "message": obj.comment,
            "rating": obj.rating,
            "category": obj.category, # e.g., "Service Quality"
            "tags": ["Appreciation"] if obj.rating >= 4 else ["Complaint"], # Logic for auto-tags
            "status": obj.status
        }

    def get_action_logs(self, obj):
        # Returns the timeline logs
        logs = obj.activity_logs.all().order_by('-created_at')
        return [
            {
                "action": log.action_text,
                "actor": log.actor.get_full_name() if log.actor else "System",
                "date": log.created_at.strftime("%Y-%m-%d %I:%M %p")
            }
            for log in logs
        ]
# apps/feedback_and_surveys/serializers.py

# --- 1. SURVEY RESPONSES TAB SERIALIZERS ---
class ResponseAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.label', read_only=True)
    class Meta:
        model = QuestionAnswer
        fields = ['question_text', 'answer_value']

class SurveyResponseCardSerializer(serializers.ModelSerializer):
    """
    Serializer for the 'Survey Responses' Tab (Image 3).
    Shows Survey Name, Customer, Date, and the Q&A list.
    """
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    customer_name = serializers.CharField(source='customer.name', default="Anonymous", read_only=True)
    date = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %I:%M %p")
    answers = ResponseAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = SurveySubmission
        fields = ['id', 'survey_title', 'customer_name', 'date', 'rating', 'comment', 'answers']


# --- 2. AUDIENCE MANAGEMENT SERIALIZERS ---
class AudienceContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = AudienceContact
        fields = ['id', 'name', 'email', 'phone', 'is_active']

class AudienceListSerializer(serializers.ModelSerializer):
    contact_count = serializers.IntegerField(source='contacts.count', read_only=True)
    class Meta:
        # Assuming you have an 'AudienceList' or 'Audience' model
        model = Survey.audience.field.related_model # Dynamically grabs your Audience model
        fields = ['id', 'name', 'description', 'contact_count', 'created_at']


# --- 3. AUTOMATION SERIALIZERS ---
class AutomationRuleSerializer(serializers.ModelSerializer):
    """
    Serializer for 'Automation & Triggers' Tab.
    """
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    
    class Meta:
        # You will need to create this model (see Step 3 below if missing)
        from .models import AutomationRule 
        model = AutomationRule
        fields = ['id', 'name', 'trigger_event', 'survey', 'survey_title', 'channel', 'is_active']