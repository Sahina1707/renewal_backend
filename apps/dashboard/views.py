from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Q
from decimal import Decimal
import uuid
import logging

from apps.renewals.models import RenewalCase
from apps.customer_payments.models import CustomerPayment
from apps.ai_insights.services import ai_service
from apps.ai_insights.models import AIConversation, AIMessage, AIAnalytics
from .serializers import DashboardSummarySerializer

logger = logging.getLogger(__name__)


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
        
        return Response({
            'success': True,
            'session_id': conversation.session_id,
            'conversation_id': conversation.id,
            'response': ai_response['response'],
            'metadata': {
                'model': ai_response.get('model'),
                'usage': ai_response.get('usage'),
                'timestamp': ai_response.get('timestamp')
            }
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
        
        return Response({
            'success': True,
            'suggestions': suggestions
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
