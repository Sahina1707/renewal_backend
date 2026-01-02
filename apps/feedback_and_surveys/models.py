from django.db import models
from django.conf import settings
from apps.core.models import BaseModel 
from django.conf import settings
class Survey(BaseModel):
    STATUS_CHOICES = [('draft', 'Draft'), ('active', 'Active'), ('completed', 'Completed'), ('paused', 'Paused')]
    SURVEY_TYPES = [
        ('csat', 'CSAT'),
        ('nps', 'NPS'),
        ('ces', 'CES'), 
        ('custom', 'Custom'),
    ]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_surveys')
    title = models.CharField(max_length=255, default="Untitled Survey")
    description = models.TextField(blank=True)
    survey_type = models.CharField(max_length=10, choices=SURVEY_TYPES, default='custom')
    is_active = models.BooleanField(default=False)
    theme = models.CharField(max_length=50, default="light")   
    language = models.CharField(max_length=10, default="en")   
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    audience = models.ForeignKey(
        'audience_manager.Audience', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='surveys',
        help_text="The specific group of users targeting for this survey."
    )
    target_audience_count = models.IntegerField(default=0) 
    
    class Meta:
        db_table = 'feedback_surveys'

class SurveyQuestion(BaseModel):
    """
    Represents an Element on the Builder Canvas.
    Updated to match the specific types shown in your video.
    """
    ELEMENT_TYPES = [
        ('single_line', 'Single-line Text'),
        ('paragraph', 'Paragraph'),
        ('dropdown', 'Dropdown'),
        ('multiple_choice', 'Multiple Choice'), 
        ('checkboxes', 'Checkboxes'),
        ('date_picker', 'Date Picker'),
        ('rating_scale', 'Rating Scale'),
        ('nps', 'Net Promoter Score'),
        ('section_break', 'Section Break'),
        ('matrix_grid', 'Matrix / Grid Question'),
        ('heading_text', 'Heading Text'),
        ('divider_line', 'Divider Line'),
    ]

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    type = models.CharField(max_length=50, choices=ELEMENT_TYPES, default='single_line')
    label = models.CharField(max_length=500, blank=True, default="Question Label")
    properties = models.JSONField(default=dict, blank=True) 
    
    order = models.IntegerField(default=0)    
    is_required = models.BooleanField(default=False) 

    class Meta:
        ordering = ['order']
        db_table = 'feedback_survey_questions'

class SurveySubmission(BaseModel):
    STATUS_CHOICES = [('unaddressed', 'Unaddressed'), ('in_progress', 'In Progress'), ('resolved', 'Resolved'),('archived','Archived')]
    CHANNEL_CHOICES = [('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('web', 'Web'),('phone','Phone'),('survey','Survey')]
    PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')]
    CATEGORY_CHOICES = [
        ('all_feedback','All Feedback'),
        ('unaddressed', 'Unaddressed'),
        ('negative/low_rating','Negative/Low Rating'),
        ('flagged_for_followup','Flagged For FollowUp'),
        ('with_attachments','With Attachements'),
        ('resolved_feedback','Resloved_Feedback'),
        ('service_quality', 'Service Quality')
    ]

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='submissions')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, null=True, blank=True)
    
    rating = models.IntegerField(default=0)
    comment = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unaddressed')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='web')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_flagged = models.BooleanField(default=False)
    sentiment_score = models.FloatField(default=0.0)     
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'feedback_survey_submissions'
class SubmissionAttachment(BaseModel):
    submission = models.ForeignKey(SurveySubmission, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='feedback/attachments/')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="Size in bytes")

    class Meta:
        db_table = 'feedback_submission_attachments'
class SubmissionActivityLog(BaseModel):
    """
    Tracks history: "Received -> Assigned to John -> Marked Resolved"
    """
    submission = models.ForeignKey(SurveySubmission, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True) 
    action= models.CharField(max_length=255)
    
    
    class Meta:
        db_table = 'feedback_submission_logs'
        ordering = ['-created_at']

class QuestionAnswer(BaseModel):
    submission = models.ForeignKey(SurveySubmission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE)
    answer_value = models.TextField() 
    
    class Meta:
        db_table = 'feedback_question_answers'
class AutomationTrigger(BaseModel):
    """
    Stores automation rules.
    Example: When 'claim_closed', send 'Survey A' via 'Email'.
    """
    TRIGGER_EVENTS = [
        ('policy_purchased', 'Policy Purchased'),
        ('claim_settled', 'Claim Settled'),
        ('ticket_closed', 'Support Ticket Closed'),
        ('renewal_completed', 'Renewal Completed'),
    ]
    
    name = models.CharField(max_length=200, help_text="Internal name for this rule")
    event_type = models.CharField(max_length=50, choices=TRIGGER_EVENTS)
    
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, help_text="Which survey to send?")
    channels = models.JSONField(default=list, help_text="List of channels e.g. ['email', 'sms']")
    
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'feedback_automation_triggers'

    def __str__(self):
        return f"{self.name} ({self.get_event_type_display()})"

class AutomationRule(BaseModel):
    TRIGGER_CHOICES = [
        ('policy_purchase', 'Policy Purchase'),      
        ('claim_settlement', 'Claim Settlement'),     
        ('support_interaction', 'Support Interaction'), 
    ]
    
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    trigger_event = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    channel = models.CharField(max_length=20, default='email') 
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.trigger_event})"