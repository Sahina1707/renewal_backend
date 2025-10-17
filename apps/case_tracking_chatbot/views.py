import json
import logging
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from apps.case_tracking_chatbot.models import (
    CaseTrackingChatbotConversation,
    CaseTrackingChatbotMessage
)
from apps.case_tracking_chatbot.services import get_case_tracking_chatbot_service
from apps.case_tracking_chatbot.serializers import (
    CaseTrackingChatbotConversationSerializer,
    CaseTrackingChatbotMessageSerializer
)

logger = logging.getLogger(__name__)


class CaseTrackingChatbotView(View):
    """Main view for case tracking chatbot functionality"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """Handle chat messages"""
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            session_id = data.get('session_id')
            
            if not user_message:
                return JsonResponse({
                    'success': False,
                    'error': 'Message is required'
                }, status=400)
            
            # Handle case where user is not authenticated (for testing)
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                conversation = None
                conversation_history = []
            else:
                conversation = self._get_or_create_conversation(user, session_id, user_message)
                conversation_history = self._get_conversation_history(conversation)
            
            case_tracking_chatbot_service = get_case_tracking_chatbot_service()
            
            if not case_tracking_chatbot_service.is_available():
                return JsonResponse({
                    'success': False,
                    'error': 'AI service not available',
                    'message': 'The AI service is currently unavailable. Please try again later.'
                }, status=503)
            
            ai_response = case_tracking_chatbot_service.generate_ai_response(
                user_message,
                conversation_history=conversation_history
            )
            
            if not ai_response.get('success'):
                return JsonResponse({
                    'success': False,
                    'error': ai_response.get('error', 'Failed to generate response'),
                    'message': ai_response.get('message', 'Unknown error occurred')
                }, status=500)
            
            # Save user message and AI response only if conversation exists
            if conversation:
                user_msg = CaseTrackingChatbotMessage.objects.create(
                    conversation=conversation,
                    role='user',
                    content=user_message
                )
                
                ai_msg = CaseTrackingChatbotMessage.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=ai_response['response'],
                    metadata={
                        'usage': ai_response.get('usage'),
                        'model': ai_response.get('model'),
                        'timestamp': ai_response.get('timestamp')
                    }
                )
                
                conversation.last_activity = timezone.now()
                conversation.update_message_count()
                conversation.save()
            
            return JsonResponse({
                'success': True,
                'session_id': conversation.session_id if conversation else None,
                'conversation_id': conversation.id if conversation else None,
                'response': ai_response['response'],
                'metadata': {
                    'model': ai_response.get('model'),
                    'usage': ai_response.get('usage'),
                    'timestamp': ai_response.get('timestamp')
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except ValidationError as e:
            logger.error(f"Validation error in chat: {e.message}")
            return JsonResponse({
                'success': False,
                'error': e.message
            }, status=400)
        except Exception as e:
            logger.exception("Error in case tracking chatbot chat endpoint")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred',
                'message': str(e)
            }, status=500)
    
    def _get_or_create_conversation(self, user, session_id, user_message):
        """Get or create conversation for the user"""
        try:
            if session_id:
                try:
                    conversation = CaseTrackingChatbotConversation.objects.get(
                        session_id=session_id,
                        user=user,
                        status='active'
                    )
                    return conversation
                except CaseTrackingChatbotConversation.DoesNotExist:
                    pass
            
            # Create new conversation
            conversation = CaseTrackingChatbotConversation.objects.create(
                user=user,
                title=user_message[:50] + '...' if len(user_message) > 50 else user_message
            )
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            return None
    
    def _get_conversation_history(self, conversation):
        """Get conversation history"""
        if not conversation:
            return []
        
        try:
            messages = conversation.messages.order_by('created_at')[:10]  
            return [
                {
                    'role': msg.role,
                    'content': msg.content
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def case_tracking_chatbot_quick_suggestions(request):
    """Get quick suggestions for case tracking chatbot"""
    try:
        service = get_case_tracking_chatbot_service()
        suggestions = service.get_quick_suggestions()
        
        return Response({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error getting quick suggestions: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to get suggestions'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def case_tracking_chatbot_conversations(request):
    """Get user's case tracking chatbot conversations"""
    try:
        conversations = CaseTrackingChatbotConversation.objects.filter(
            user=request.user,
            status='active'
        ).order_by('-last_activity')
        
        serializer = CaseTrackingChatbotConversationSerializer(conversations, many=True)
        
        return Response({
            'success': True,
            'conversations': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to get conversations'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def case_tracking_chatbot_conversation_detail(request, conversation_id):
    """Get detailed conversation with messages"""
    try:
        conversation = CaseTrackingChatbotConversation.objects.get(
            id=conversation_id,
            user=request.user,
            status='active'
        )
        
        serializer = CaseTrackingChatbotConversationSerializer(conversation)
        
        return Response({
            'success': True,
            'conversation': serializer.data
        })
        
    except CaseTrackingChatbotConversation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Conversation not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting conversation detail: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to get conversation'
        }, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def case_tracking_chatbot_delete_conversation(request, conversation_id):
    """Delete a conversation"""
    try:
        conversation = CaseTrackingChatbotConversation.objects.get(
            id=conversation_id,
            user=request.user,
            status='active'
        )
        
        conversation.status = 'deleted'
        conversation.save()
        
        return Response({
            'success': True,
            'message': 'Conversation deleted successfully'
        })
        
    except CaseTrackingChatbotConversation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Conversation not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to delete conversation'
        }, status=500)


@api_view(['GET'])
def case_tracking_chatbot_status(request):
    """Check case tracking chatbot service status"""
    try:
        service = get_case_tracking_chatbot_service()
        is_available = service.is_available()
        
        return Response({
            'success': True,
            'available': is_available,
            'message': 'Case tracking chatbot service is available' if is_available else 'Case tracking chatbot service is not available'
        })
        
    except Exception as e:
        logger.error(f"Error checking service status: {str(e)}")
        return Response({
            'success': False,
            'available': False,
            'error': 'Failed to check service status'
        }, status=500)
