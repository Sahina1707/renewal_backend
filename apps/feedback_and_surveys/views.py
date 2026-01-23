from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from .models import Survey, SurveySubmission, SurveyQuestion, QuestionAnswer, SubmissionAttachment, SubmissionActivityLog, AutomationRule
from .serializers import InboxSubmissionSerializer, SurveySerializer, SurveySubmissionSerializer, SurveyCampaignSerializer, DashboardFeedbackTableSerializer, FeedbackDetailSerializer, SurveyResponseCardSerializer, AudienceListSerializer, AudienceContactSerializer, AutomationRuleSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Avg, Count, Sum
from .services import DistributionService
import csv
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from django.db.models import Case, When
from django.db.models.functions import TruncDate
from apps.audience_manager.models import AudienceContact
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.utils import timezone

class SurveyViewSet(viewsets.ModelViewSet):
    serializer_class = SurveySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Survey.objects.filter(owner=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        survey = serializer.save(owner=self.request.user)
        if survey.audience:
            survey.target_audience_count = survey.audience.contact_count
            survey.save()

    def perform_update(self, serializer):
        survey = serializer.save()
        if survey.audience:
            survey.target_audience_count = survey.audience.contact_count
            survey.save()

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Endpoint for the 'Publish' button.
        Sets status to 'active' and generates the public link.
        """
        survey = self.get_object()
        survey.status = 'active'
        survey.is_active = True
        survey.save()
        
        return Response({
            'status': 'published',
            'public_link': f"https://your-domain.com/surveys/{survey.id}",
            'message': 'Survey is now live!'
        })
    @action(detail=True, methods=['post'])
    def launch(self, request, pk=None):
        """
        Triggers the DistributionService to send emails/SMS.
        Endpoint: POST /surveys/{id}/launch/
        """
        survey = self.get_object()
        
        # Get channels from request (e.g., ["email", "sms"])
        channels = request.data.get('channels', ['email'])
        
        service = DistributionService(survey)
        result = service.launch_campaign(channels=channels)
        
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(result, status=status.HTTP_200_OK)
    @action(detail=True, methods=['get'])
    def export_csv(self, request, pk=None):
        """
        Downloads all responses for a specific survey as CSV.
        URL: GET /api/feedback/surveys/{id}/export_csv/
        """
        survey = self.get_object()
        submissions = survey.submissions.all().order_by('-created_at')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{survey.title}_results.csv"'
        
        writer = csv.writer(response)
        
        # Dynamic Headers based on Questions
        question_labels = [q.label for q in survey.questions.all().order_by('order')]
        headers = ['Date', 'Customer', 'Rating', 'Comment'] + question_labels
        writer.writerow(headers)
        
        for sub in submissions:
            # Basic Info
            row = [
                sub.created_at.strftime("%Y-%m-%d"),
                sub.customer.name if sub.customer else sub.customer_name or "Anonymous",
                sub.rating,
                sub.comment
            ]
            
            # Match Answers to Questions (Handle missing answers)
            # We fetch all answers for this submission
            answers_map = {ans.question_id: ans.answer_value for ans in sub.answers.all()}
            
            for question in survey.questions.all().order_by('order'):
                row.append(answers_map.get(question.id, "")) # Empty string if no answer
            
            writer.writerow(row)
            
        return response
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """
        Endpoint for the 'Pause' button on the Campaign Card.
        Sets status to 'paused' and stops public access.
        """
        survey = self.get_object()
        survey.status = 'paused'
        survey.is_active = False
        survey.save()
        
        return Response({'status': 'paused', 'message': 'Survey campaign paused.'})

    @action(detail=True, methods=['get'])
    def export_pdf(self, request, pk=None):
        """
        Generates a PDF summary report.
        URL: GET /api/feedback/surveys/{id}/export_pdf/
        """
        survey = self.get_object()
        submissions = survey.submissions.all()
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{survey.title}_report.pdf"'
        
        # Setup PDF Document
        doc = SimpleDocTemplate(response, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # 1. Title
        elements.append(Paragraph(f"Survey Report: {survey.title}", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # 2. Stats Section
        total = submissions.count()
        avg = submissions.aggregate(Avg('rating'))['rating__avg'] or 0
        stats_text = f"Total Responses: {total}  |  Average Rating: {round(avg, 1)} / 5"
        elements.append(Paragraph(stats_text, styles['Heading2']))
        elements.append(Spacer(1, 12))
        
        # 3. Table of Recent Responses
        data = [['Date', 'Customer', 'Rating', 'Comment']] # Header
        
        # Add top 20 rows (to avoid crashing PDF with 10k rows)
        for sub in submissions[:20]:
            name = sub.customer.name if sub.customer else "Anonymous"
            # Truncate long comments
            comment = (sub.comment[:50] + '...') if sub.comment and len(sub.comment) > 50 else sub.comment or ""
            data.append([
                sub.created_at.strftime("%Y-%m-%d"),
                name,
                str(sub.rating),
                comment
            ])
            
        # Table Styling
        table = Table(data, colWidths=[80, 100, 50, 250])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("(Showing last 20 responses)", styles['Italic']))
        
        doc.build(elements)
        return response
    
class FeedbackDashboardView(APIView):
    """
    SINGLE API for the 'Dashboard' Tab.
    URL: GET /api/feedback/dashboard-stats/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_surveys = Survey.objects.filter(owner=request.user)
        user_submissions = SurveySubmission.objects.filter(survey__owner=request.user)
        total_feedback = user_submissions.count()
        avg_rating = user_submissions.aggregate(Avg('rating'))['rating__avg'] or 0
        promoters = user_submissions.filter(rating__gte=9).count()
        detractors = user_submissions.filter(rating__lte=6).count()
        nps_score = ((promoters - detractors) / total_feedback * 100) if total_feedback > 0 else 0
        
        avg_sentiment = user_submissions.aggregate(Avg('sentiment_score'))['sentiment_score__avg'] or 0
        sentiment_score_normalized = int((avg_sentiment + 1) * 50) 

        total_targeted = user_surveys.aggregate(Sum('target_audience_count'))['target_audience_count__sum'] or 0
        if total_targeted > 0:
            completion_rate = round((total_feedback / total_targeted) * 100, 1)
        else:
            completion_rate = 0.0

        # --- Attention Widget Stats ---
        status_counts = user_submissions.values('status').annotate(count=Count('status'))
        unaddressed = next((item['count'] for item in status_counts if item['status'] == 'unaddressed'), 0)
        flagged = user_submissions.filter(rating__lte=2).count() 
        negative = detractors

        # --- Charts Data ---
        recent_trends = user_submissions.order_by('-created_at')[:10].values('created_at', 'rating')
        categories = user_submissions.values('category').annotate(count=Count('category'))

        # --- Recent Feedback Table ---
        recent_items = user_submissions.order_by('-created_at')[:5]
        table_serializer = DashboardFeedbackTableSerializer(recent_items, many=True)

        return Response({
            "kpi_overview": {   
                "overall_satisfaction": round(avg_rating, 1),
                "nps_score": round(nps_score),
                "survey_completion_rate": completion_rate,
                "total_feedback": total_feedback,
                "sentiment_score": sentiment_score_normalized,
                "flagged_feedback": flagged,
                "negative_feedback": negative
            },
            
            "attention_required": {
                "unaddressed_count": unaddressed,
                "flagged_items": flagged,
                "negative_feedback": negative
            },
            "recent_feedback": table_serializer.data 
        })
class CampaignViewSet(viewsets.ModelViewSet):
    """
    API for 'Survey Campaigns' Tab.
    """
    serializer_class = SurveyCampaignSerializer 
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title']

    def get_queryset(self):
        return Survey.objects.filter(owner=self.request.user).annotate(
            response_count=Count('submissions')
        ).order_by('-created_at')
class SubmissionViewSet(viewsets.ModelViewSet):
    """
    API for 'Feedback Inbox' Tab.
    Supports advanced filtering: ?status=unaddressed & ?rating__lte=2 & ?created_at__gte=...
    """
    serializer_class = InboxSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = {
        'status': ['exact'],
        'priority': ['exact'],      
        'is_flagged': ['exact'],    
        'rating': ['exact', 'gte', 'lte'],
        'channel': ['exact'],
        'assigned_to': ['exact'],   
        'created_at': ['gte', 'lte'],
    }
    
    search_fields = [
        'comment', 
        'customer__first_name', 
        'customer__last_name', 
        'customer__email'
    ]

    def get_queryset(self):
        """
        Return only submissions for surveys owned by the logged-in user.
        """
        user = self.request.user
        if user.is_anonymous:
            return SurveySubmission.objects.none()
            
        return SurveySubmission.objects.filter(survey__owner=user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        submission = self.get_object()
        submission.status = 'resolved' 
        submission.save()
        return Response({'status': 'Reply sent', 'new_status': 'resolved'})

    @action(detail=True, methods=['patch'])
    def assign(self, request, pk=None):
        submission = self.get_object()
        agent_id = request.data.get('assigned_to')
        submission.assigned_to_id = agent_id
        submission.status = 'in_progress'
        submission.save()
        return Response({'status': 'assigned', 'agent': agent_id})
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """
        API: POST /api/feedback_and_surveys/inbox/{id}/archive/
        Moves a specific feedback to the 'Archived' list.
        """
        submission = self.get_object()
        submission.status = 'archived'
        submission.save()
        self._log_activity(submission, request.user, "Archived this feedback")
        
        return Response({'status': 'success', 'message': 'Feedback moved to archive.'})

    @action(detail=False, methods=['get'])
    def archived_list(self, request):
        """
        API: GET /api/feedback_and_surveys/inbox/archived_list/
        Returns ONLY archived items (for the 'Archived' tab in UI).
        """
        user = self.request.user
        submissions = SurveySubmission.objects.filter(
            survey__owner=user, 
            status='archived'
        ).order_by('-created_at')
        
        serializer = self.get_serializer(submissions, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """
        Handles ALL bulk operations: Assign, Resolve, Flag, Archive.
        Payload: { "ids": [1, 2], "action": "assign", "value": 5 }
        """
        ids = request.data.get('ids', [])
        action_type = request.data.get('action')
        value = request.data.get('value') # Used for 'assign' (User ID)

        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)

        submissions = SurveySubmission.objects.filter(id__in=ids)
        count = 0

        for sub in submissions:
            if action_type == 'assign':
                if value:
                    sub.assigned_to_id = value
                    sub.status = 'in_progress' # Auto-update status when assigned
                    sub.save()
                    self._log_activity(sub, request.user, f"Bulk assigned to User {value}")
                    count += 1
            
            elif action_type == 'resolve':
                sub.status = 'resolved'
                sub.save()
                self._log_activity(sub, request.user, "Marked resolved (Bulk)")
                count += 1

            elif action_type == 'flag':
                sub.is_flagged = True
                sub.save()
                self._log_activity(sub, request.user, "Flagged for follow-up (Bulk)")
                count += 1
                
            elif action_type == 'archive':
                sub.status = 'archived'
                sub.save()
                self._log_activity(sub, request.user, "Archived (Bulk)")
                count += 1

        return Response({'status': 'success', 'updated_count': count, 'action': action_type})

  
    def _log_activity(self, submission, user, text):
        """Helper to create log entry"""
        SubmissionActivityLog.objects.create(
            submission=submission,
            actor=user,
            action=text,  
            created_at=timezone.now()
        )
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Exports the CURRENT filtered inbox to CSV.
        URL: GET /api/feedback/inbox/export/?status=unaddressed&rating__lte=2
        """
        # 1. Apply the same filters used in the UI
        queryset = self.filter_queryset(self.get_queryset())
        
        # 2. Create the Response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="feedback_inbox.csv"'
        
        # 3. Write CSV Data
        writer = csv.writer(response)
        writer.writerow(['ID', 'Date', 'Customer', 'Rating', 'Category', 'Status', 'Comment', 'Assigned To'])
        
        for sub in queryset:
            writer.writerow([
                sub.id,
                sub.created_at.strftime("%Y-%m-%d %H:%M"),
                sub.customer.name if sub.customer else "Anonymous",
                f"{sub.rating}/5",
                sub.category,
                sub.get_status_display(),
                sub.comment,
                sub.assigned_to.get_full_name() if sub.assigned_to else "Unassigned"
            ])
            
        return response

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Handles selecting multiple rows and clicking "Mark Resolved" or "Bulk Assign".
        Payload: { "ids": [1, 2, 3], "action": "resolve" }
        """
        ids = request.data.get('ids', [])
        action_type = request.data.get('action')
        value = request.data.get('value') 
        submissions = SurveySubmission.objects.filter(id__in=ids)
        updated_count = 0

        for sub in submissions:
            if action_type == 'resolve':
                sub.status = 'resolved'
                sub.save()
                self._log_activity(sub, request.user, "Marked as Resolved (Bulk Action)")
                updated_count += 1
                
            elif action_type == 'assign':
                if value:
                    sub.assigned_to_id = value
                    sub.save()
                    self._log_activity(sub, request.user, f"Assigned to User ID {value}")
                    updated_count += 1
            
            elif action_type == 'flag':
                sub.is_flagged = True
                sub.save()
                self._log_activity(sub, request.user, "Flagged for follow-up")
                updated_count += 1

        return Response({'message': f'Successfully updated {updated_count} items.'})

    def perform_update(self, serializer):
        instance = serializer.save()
        if 'status' in serializer.validated_data:
            self._log_activity(instance, self.request.user, f"Changed status to {instance.status}")
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FeedbackDetailSerializer  
        return InboxSubmissionSerializer
    @action(detail=False, methods=['get'])
    def inbox_stats(self, request):
        """
        API: GET /api/feedback_and_surveys/inbox/inbox_stats/
        Returns counts for the header cards (Unaddressed, Negative, etc.).
        """
        queryset = self.get_queryset()
        data = {
            "all_feedback": queryset.count(),
            "unaddressed": queryset.filter(status='unaddressed').count(),
            "negative": queryset.filter(rating__lte=2).count(),
            "flagged": queryset.filter(is_flagged=True).count(),
            "with_attachments": queryset.filter(attachments__isnull=False).distinct().count(),
            "resolved": queryset.filter(status='resolved').count()
        }
        
        return Response(data)
    
class PublicSurveyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = Survey.objects.filter(status='active') 
    serializer_class = SurveySerializer
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        survey = self.get_object()
        data = request.data
        
        customer_name = "Anonymous"
        customer_obj = None
        contact_id = request.query_params.get('c') 
        
        if contact_id:
            try:
                contact = AudienceContact.objects.get(id=contact_id)
                customer_name = contact.name
                customer_obj = contact.customer 
            except AudienceContact.DoesNotExist:
                pass

       
        submission_data = {
            "survey": survey.id,
            "rating": data.get('rating', 0),
            "comment": data.get('comment', ""),
            "customer_name": customer_name,
            "customer": customer_obj.id if customer_obj else None, 
        }

        serializer = SurveySubmissionSerializer(data=submission_data)
        if serializer.is_valid():
            submission = serializer.save()
            raw_answers = data.get('answers', [])
            for ans in raw_answers:
                try:
                    question = SurveyQuestion.objects.get(id=ans['question_id'])
                    QuestionAnswer.objects.create(
                        submission=submission,
                        question=question,
                        answer_value=str(ans['value'])
                    )
                except SurveyQuestion.DoesNotExist:
                    continue
            return Response({'status': 'success', 'message': 'Thank you for your feedback!'}, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class FeedbackAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        params = request.query_params
        queryset = SurveySubmission.objects.filter(survey__owner=request.user)
        
        if params.get('date_from'):
            queryset = queryset.filter(created_at__date__gte=params.get('date_from'))
        if params.get('date_to'):
            queryset = queryset.filter(created_at__date__lte=params.get('date_to'))
        if params.get('survey_id'):
            queryset = queryset.filter(survey_id=params.get('survey_id'))
        total_responses = queryset.count()
        avg_csat = queryset.aggregate(Avg('rating'))['rating__avg'] or 0
        flagged_count = queryset.filter(is_flagged=True).count() 
        negative_count = queryset.filter(rating__lte=2).count()           
        # NPS Calculation (Keep existing)
        promoters = queryset.filter(rating__gte=9).count()
        detractors = queryset.filter(rating__lte=6).count()
        nps_score = ((promoters - detractors) / total_responses * 100) if total_responses > 0 else 0
        # 3. Charts Data (Keep existing)
        sentiment_stats = queryset.aggregate(
            positive=Count(Case(When(sentiment_score__gt=0.3, then=1))),
            neutral=Count(Case(When(sentiment_score__range=(-0.3, 0.3), then=1))),
            negative=Count(Case(When(sentiment_score__lt=-0.3, then=1)))
        )
        priority_stats = queryset.values('priority').annotate(count=Count('id')).order_by('-count')
        daily_trends = queryset.annotate(date=TruncDate('created_at')).values('date').annotate(
            avg_rating=Avg('rating'),
            count=Count('id')
        ).order_by('date')
        channel_performance = queryset.values('channel').annotate(
            count=Count('id'),
            avg_rating=Avg('rating')
        ).order_by('-count')
        return Response({
            "kpi": {
                "total_responses": total_responses,
                "avg_csat": round(avg_csat, 1),
                "nps_score": round(nps_score),
                "flagged_count": flagged_count,   
                "negative_count": negative_count, 
            },
            "charts": {
                "sentiment_distribution": sentiment_stats,
                "priority_breakdown": priority_stats, 
                "daily_trends": daily_trends,
                "channel_performance": channel_performance
            }
        })
class DistributionChannelViewSet(viewsets.ViewSet):
    """
    API for the 'Distribution Channels' Tab.
    URL: GET /api/feedback/channels/
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        # You can replace these hardcoded values with database checks later
        channels = [
            {
                "id": "email",
                "name": "Email",
                "status": "active",
                "icon": "mail",
                "description": "Send surveys via email campaigns."
            },
            {
                "id": "sms",
                "name": "SMS",
                "status": "active", 
                "icon": "message-square",
                "description": "Send survey links via SMS."
            },
            {
                "id": "whatsapp",
                "name": "WhatsApp",
                "status": "inactive",
                "icon": "message-circle",
                "description": "Share surveys on WhatsApp."
            }
        ]
        return Response(channels)
class PublicSurveyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, survey_id, format=None):
        # ... (Keep your existing GET logic) ...
        survey = get_object_or_404(Survey, id=survey_id)
        serializer = SurveySerializer(survey)
        return Response(serializer.data)

    def post(self, request, survey_id, format=None):
        survey = get_object_or_404(Survey, id=survey_id)
        
        # 1. Get the Contact ID from URL (?c=9)
        contact_id = request.query_params.get('c')
        customer_obj = None

        # 2. Look up the AudienceContact
        if contact_id:
            try:
                # Assuming your AudienceContact uses integer IDs. 
                # We fetch the .customer from the contact to link it correctly.
                customer_obj = AudienceContact.objects.get(id=contact_id).customer
            except (AudienceContact.DoesNotExist, ValueError, AttributeError):
                pass # If ID is invalid or not found, keep it Anonymous
        
        # 3. Create Submission with the Customer
        data = request.data
        submission = SurveySubmission.objects.create(
            survey=survey,
            rating=data.get('rating'),
            comment=data.get('comment', ''),
            customer=customer_obj,  # <--- SAVE THE CUSTOMER HERE
            status='unaddressed'
        )

        return Response({"message": "Feedback received!"}, status=status.HTTP_201_CREATED)
class ResponseListViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for 'Survey Responses' Tab.
    URL: /api/feedback_and_surveys/responses/
    """
    serializer_class = SurveyResponseCardSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['survey', 'rating'] # Filter by specific survey
    ordering = ['-created_at']

    def get_queryset(self):
        # Only show responses for surveys owned by this user
        return SurveySubmission.objects.filter(survey__owner=self.request.user)

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """
        Global Export CSV for the 'Survey Responses' tab.
        Downloads ALL filtered responses.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="all_responses.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Survey', 'Date', 'Customer', 'Rating', 'Comment', 'Answers'])
        
        for sub in queryset:
            # Format answers as a string "Q: A | Q: A"
            answers_str = " | ".join([f"{a.question.label}: {a.answer_value}" for a in sub.answers.all()])
            customer = sub.customer.name if sub.customer else "Anonymous"
            
            writer.writerow([
                sub.survey.title,
                sub.created_at.strftime("%Y-%m-%d"),
                customer,
                sub.rating,
                sub.comment,
                answers_str
            ])
        return response

    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """
        Global Export PDF for the 'Survey Responses' tab.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="all_responses_report.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("Survey Responses Report", styles['Title']))
        elements.append(Spacer(1, 12))
        
        data = [['Survey', 'Customer', 'Rating', 'Comment']]
        for sub in queryset[:50]: # Limit to 50 for performance safety in PDF
            customer = sub.customer.name if sub.customer else "Anonymous"
            comment = (sub.comment[:50] + '...') if sub.comment else "-"
            data.append([sub.survey.title, customer, str(sub.rating), comment])
            
        table = Table(data, colWidths=[150, 100, 50, 200])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
        ]))
        
        elements.append(table)
        doc.build(elements)
        return response


# --- 2. AUDIENCE MANAGEMENT VIEWSET ---
class AudienceViewSet(viewsets.ModelViewSet):
    """
    API for 'Audience Management' Tab.
    URL: /api/feedback_and_surveys/audiences/
    """
    # Assuming 'Audience' is the model name for your contact lists
    # Replace 'Audience' with your actual model class if different
    from apps.audience_manager.models import Audience 
    queryset = Audience.objects.all()
    serializer_class = AudienceListSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Get all contacts inside a specific audience list"""
        audience = self.get_object()
        contacts = audience.contacts.all()
        serializer = AudienceContactSerializer(contacts, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        active_customers = AudienceContact.objects.count()
        participants = SurveySubmission.objects.values('customer').distinct().count()

        return Response({
            "active_customers": active_customers,
            "survey_participants": participants
        })
class AutomationViewSet(viewsets.ModelViewSet):
    """
    API for 'Automation & Triggers' Tab.
    URL: /api/feedback_and_surveys/automation/
    """
    serializer_class = AutomationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AutomationRule.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)