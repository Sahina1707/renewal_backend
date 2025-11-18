from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Q
from decimal import Decimal
import uuid
import logging
from django.utils import timezone
from datetime import timedelta
from apps.renewals.models import RenewalCase
from apps.customer_payments.models import CustomerPayment
from apps.ai_insights.services import ai_service
from apps.ai_insights.models import AIConversation, AIMessage, AIAnalytics
from .serializers import DashboardSummarySerializer

logger = logging.getLogger(__name__)


def generate_related_suggestions(user_message, ai_response):
    """
    Generate 3 related suggestions based on the user's question and AI response
    """
    all_suggestions = [
        "What is my renewal case status?",
        "Show me my payment history",
        "What is my policy information?",
        "What is my total renewal amount?",
        "When is my policy expiring?",
        "What is the renewal amount?",
        "What is my payment status?",
        "Who is assigned to my case?",
        "What are the recent updates?",
        "When is the payment due?",
        "What is my case status?",
        "Show me my case history",
        "What is my policy status?",
        "When does my policy expire?",
        "Show me my renewal cases",
        "Give me a case summary",
        "What are my active policies?",
        "Show me my policy details",
        "What is my customer information?",
        "Give me a dashboard overview"
    ]
    
    message_lower = user_message.lower()
    
    if 'payment' in message_lower or 'paid' in message_lower:
        context_suggestions = [
            "What is my total renewal amount?",
            "Show me my payment history",
            "What is the status of my renewal case?"
        ]
    
    elif 'renewal' in message_lower or 'renew' in message_lower:
        context_suggestions = [
            "What is my renewal case status?",
            "When is my policy expiring?",
            "What is the renewal amount?"
        ]
    
    elif 'status' in message_lower or 'progress' in message_lower:
        context_suggestions = [
            "What is my payment status?",
            "Who is assigned to my case?",
            "What are the recent updates?"
        ]
    
    elif 'amount' in message_lower or 'cost' in message_lower or 'price' in message_lower:
        context_suggestions = [
            "What is my payment status?",
            "When is the payment due?",
            "What is my renewal case status?"
        ]
    
    elif 'case' in message_lower or 'cases' in message_lower:
        context_suggestions = [
            "What is my case status?",
            "Show me my case history",
            "What is the renewal amount?"
        ]
    
    elif 'policy' in message_lower or 'policies' in message_lower:
        context_suggestions = [
            "What is my policy status?",
            "When does my policy expire?",
            "What is the renewal amount?"
        ]
    
    elif 'customer' in message_lower or 'my' in message_lower:
        context_suggestions = [
            "What is my renewal case status?",
            "Show me my payment history",
            "What is my policy information?"
        ]
    
    elif 'dashboard' in message_lower or 'summary' in message_lower or 'overview' in message_lower:
        context_suggestions = [
            "Show me my renewal cases",
            "What is my payment status?",
            "Give me a case summary"
        ]
    
    else:
        context_suggestions = [
            "What is my renewal case status?",
            "Show me my payment history",
            "What is my policy information?"
        ]
    
    final_suggestions = []
    for suggestion in context_suggestions:
        if suggestion.lower() not in message_lower:
            final_suggestions.append(suggestion)
    
    while len(final_suggestions) < 3 and all_suggestions:
        suggestion = all_suggestions.pop(0)
        if suggestion.lower() not in message_lower and suggestion not in final_suggestions:
            final_suggestions.append(suggestion)
    
    return final_suggestions[:3]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    try:
        
        renewal_cases = RenewalCase.objects.filter(is_deleted=False)
        
        total_cases = renewal_cases.count()
        in_progress = renewal_cases.filter(status='in_progress').count()
        renewed = renewal_cases.filter(status='renewed').count()
        pending_action = renewal_cases.filter(status='pending_action').count()
        failed = renewal_cases.filter(status='failed').count()
        
        renewal_amount_total = renewal_cases.aggregate(
            total=Sum('renewal_amount')
        )['total'] or Decimal('0.00')
        
        payment_collected = CustomerPayment.objects.filter(
            is_deleted=False,
            payment_status='completed'
        ).aggregate(
            total=Sum('payment_amount')
        )['total'] or Decimal('0.00')
        
        payment_pending = renewal_amount_total - payment_collected
        
        dashboard_data = {
            'total_cases': total_cases,
            'in_progress': in_progress,
            'renewed': renewed,
            'pending_action': pending_action,
            'failed': failed,
            'renewal_amount_total': renewal_amount_total,
            'payment_collected': payment_collected,
            'payment_pending': payment_pending
        }
        
        serializer = DashboardSummarySerializer(dashboard_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch dashboard data: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_chat(request):
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        
        if not message:
            return Response(
                {'error': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not ai_service.is_available():
            return Response(
                {
                    'error': 'AI service not available',
                    'message': 'OpenAI API key not configured or service unavailable'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        conversation = None
        if session_id:
            try:
                conversation = AIConversation.objects.get(
                    session_id=session_id,
                    user=request.user,
                    status='active'
                )
            except AIConversation.DoesNotExist:
                pass
        
        if not conversation:
            session_id = str(uuid.uuid4())
            conversation = AIConversation.objects.create(
                user=request.user,
                session_id=session_id,
                title=message[:50] + "..." if len(message) > 50 else message,
                status='active'
            )
        
        user_message = AIMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
        
        conversation_history = []
        if conversation:
            recent_messages = conversation.messages.all().order_by('-timestamp')[:5]
            for msg in recent_messages:
                conversation_history.append({
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                })
        
        ai_response = ai_service.generate_ai_response(
            message, 
            user=request.user,
            conversation_history=conversation_history
        )
        
        if not ai_response.get('success'):
            return Response(
                {
                    'error': 'Failed to generate AI response',
                    'message': ai_response.get('message', 'Unknown error')
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        assistant_message = AIMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=ai_response['response'],
            metadata={
                'model': ai_response.get('model'),
                'usage': ai_response.get('usage'),
                'timestamp': ai_response.get('timestamp')
            }
        )
        
        conversation.update_message_count()
        
        cleaned_response = ai_response['response'].replace('\n\n', ' ').replace('\n', ' ').strip()
        import re
        cleaned_response = re.sub(r'\s+', ' ', cleaned_response)
        phrase_replacements = [
            ('Based on the current system data provided', 'Based on my analysis'),
            ('Based on current system data provided', 'Based on my analysis'),
            ('Based on the system data provided', 'Based on my analysis'),
            ('Based on system data provided', 'Based on my analysis'),
            ('Based on the data provided', 'Based on my analysis'),
            ('Based on data provided', 'Based on my analysis'),
            ('From the data provided', 'Based on my analysis'),
            ('From the information provided', 'Based on my analysis'),
            ('Based on the information provided', 'Based on my analysis'),
            ('Based on the available data', 'Based on my analysis'),
            ('Based on available data', 'Based on my analysis'),
            ('From the available data', 'Based on my analysis'),
            ('Based on the current data', 'Based on my analysis'),
            ('Based on current data', 'Based on my analysis'),
            ('From the current data', 'Based on my analysis'),
            ('Based on the system data', 'Based on my analysis'),
            ('Based on system data', 'Based on my analysis'),
            ('From the system data', 'Based on my analysis'),
            ('Based on the current system data', 'Based on my analysis'),
            ('Based on current system data', 'Based on my analysis'),
            ('From the current system data', 'Based on my analysis')
        ]
        for old, new in phrase_replacements:
            if old in cleaned_response:
                cleaned_response = cleaned_response.replace(old, new)
        
        return Response({
            'response': cleaned_response
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in AI chat: {str(e)}")
        return Response(
            {'error': f'Failed to process AI chat: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_suggestions(request):
    try:
        suggestions = ai_service.get_quick_suggestions()
        
        # Extract only titles from suggestions
        title_suggestions = []
        for suggestion in suggestions:
            if isinstance(suggestion, dict) and 'title' in suggestion:
                title_suggestions.append(suggestion['title'])
            elif isinstance(suggestion, str):
                title_suggestions.append(suggestion)
        
        return Response({
            'success': True,
            'suggestions': title_suggestions
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching AI suggestions: {str(e)}")
        return Response(
            {'error': f'Failed to fetch suggestions: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_analytics(request):
    try:
        analytics_type = request.GET.get('type', 'dashboard_summary')

        if not ai_service.is_available():
            return Response(
                {
                    'error': 'AI service not available',
                    'message': 'OpenAI API key not configured or service unavailable'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
       
        dashboard_data = ai_service.get_dashboard_data()
        
        if analytics_type == 'renewal_analysis':
            analysis_result = ai_service.analyze_renewal_performance()
            
            if analysis_result.get('success'):
                analytics = AIAnalytics.objects.create(
                    user=request.user,
                    analytics_type='renewal_analysis',
                    title='Renewal Performance Analysis',
                    summary=f"Renewal rate: {analysis_result['metrics']['renewal_rate']}%, Success rate: {analysis_result['metrics']['success_rate']}%",
                    detailed_analysis=analysis_result['metrics'],
                    insights=analysis_result['insights'],
                    recommendations=analysis_result['recommendations'],
                    data_snapshot=dashboard_data
                )
                
                return Response({
                    'success': True,
                    'analytics': {
                        'id': analytics.id,
                        'type': analytics.analytics_type,
                        'title': analytics.title,
                        'summary': analytics.summary,
                        'metrics': analytics.detailed_analysis,
                        'insights': analytics.insights,
                        'recommendations': analytics.recommendations,
                        'generated_at': analytics.generated_at.isoformat()
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {
                        'error': 'Failed to analyze renewal performance',
                        'message': analysis_result.get('error', 'Unknown error')
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        else:
            return Response({
                'success': True,
                'data': dashboard_data,
                'message': 'Dashboard data retrieved successfully'
            }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in AI analytics: {str(e)}")
        return Response(
            {'error': f'Failed to generate analytics: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_conversations(request):
    try:
        conversations = AIConversation.objects.filter(
            user=request.user,
            status='active'
        ).order_by('-last_activity')[:10]  
        
        conversation_list = []
        for conv in conversations:
            conversation_list.append({
                'id': conv.id,
                'session_id': conv.session_id,
                'title': conv.title,
                'message_count': conv.message_count,
                'started_at': conv.started_at.isoformat(),
                'last_activity': conv.last_activity.isoformat()
            })
        
        return Response({
            'success': True,
            'conversations': conversation_list
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching conversations: {str(e)}")
        return Response(
            {'error': f'Failed to fetch conversations: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_conversation_messages(request, session_id):
    try:
        conversation = AIConversation.objects.get(
            session_id=session_id,
            user=request.user,
            status='active'
        )
        
        messages = conversation.messages.all().order_by('timestamp')
        
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'metadata': msg.metadata
            })
        
        return Response({
            'success': True,
            'conversation': {
                'id': conversation.id,
                'session_id': conversation.session_id,
                'title': conversation.title,
                'started_at': conversation.started_at.isoformat()
            },
            'messages': message_list
        }, status=status.HTTP_200_OK)
        
    except AIConversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching conversation messages: {str(e)}")
        return Response(
            {'error': f'Failed to fetch messages: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_status(request):
    try:
        is_available = ai_service.is_available()
        
        return Response({
            'success': True,
            'ai_available': is_available,
            'message': 'AI service is available' if is_available else 'AI service is not available - check OpenAI API key configuration'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error checking AI status: {str(e)}")
        return Response(
            {'error': f'Failed to check AI status: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_filtered(request):
    try:
        date_range = request.GET.get('date_range', '').lower()
        policy_type = request.GET.get('policy_type', '').lower()
        status_filter = request.GET.get('status', '').lower()
        team = request.GET.get('team', '').lower()

        renewal_cases = RenewalCase.objects.filter(is_deleted=False)

        today = timezone.now().date()

        if date_range == 'daily':
            renewal_cases = renewal_cases.filter(created_at__date=today)

        elif date_range == 'weekly':
            week_start = today - timedelta(days=today.weekday())
            renewal_cases = renewal_cases.filter(created_at__date__gte=week_start)

        elif date_range == 'monthly':
            renewal_cases = renewal_cases.filter(created_at__month=today.month)

        elif date_range == 'custom':
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            if start_date and end_date:
                renewal_cases = renewal_cases.filter(created_at__date__range=[start_date, end_date])

        if policy_type and policy_type != 'all':
            renewal_cases = renewal_cases.filter(
                Q(policy__policy_type__name__iexact=policy_type) |
                Q(policy__policy_type__code__iexact=policy_type) |
                Q(policy__policy_type__category__iexact=policy_type)
            )

        # Status filter (already correct)
        if status_filter and status_filter != 'all':
            renewal_cases = renewal_cases.filter(status__iexact=status_filter)

        # Team filter
        if team and team != 'all':
            renewal_cases = renewal_cases.filter(channel__name__iexact=team)

        summary = {
            "total_cases": renewal_cases.count(),
            "in_progress": renewal_cases.filter(status='in_progress').count(),
            "renewed": renewal_cases.filter(status='renewed').count(),
            "pending_action": renewal_cases.filter(status='pending_action').count(),
            "failed": renewal_cases.filter(status='failed').count(),
            "total_revenue": renewal_cases.filter(status='renewed').aggregate(total=Sum('renewal_amount'))["total"] or Decimal('0.00')
        }

        channel_data = []
        from apps.channels.models import Channel

        channels = Channel.objects.filter(is_deleted=False)

        for channel in channels:
            channel_cases = renewal_cases.filter(channel=channel)
            renewed_cases = channel_cases.filter(status='renewed')

            total = channel_cases.count()
            renewed_count = renewed_cases.count()

            revenue = renewed_cases.aggregate(total=Sum('renewal_amount'))['total'] or 0
            budget = float(channel.budget or 0)

            conversion = round((renewed_count / total) * 100, 1) if total > 0 else 0
            efficiency = round(min(100.0, (float(revenue) / budget) * 100), 1) if budget > 0 else 0

            channel_data.append({
                "channel_name": channel.name,
                "type": channel.channel_type,
                "manager": channel.manager_name,
                "cases": total,
                "renewed": renewed_count,
                "conversion": conversion,
                "efficiency": efficiency,
                "revenue": f"{float(revenue):.2f}"
            })

        return Response({
            "success": True,
            "filters_applied": {
                "date_range": date_range,
                "policy_type": policy_type,
                "status": status_filter,
                "team": team
            },
            "summary": summary,
            "channels": channel_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
