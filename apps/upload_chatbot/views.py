import json
import logging
import uuid
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.upload_chatbot.models import UploadChatbotConversation, UploadChatbotMessage
from apps.upload_chatbot.services import get_upload_chatbot_service
from apps.upload_chatbot.serializers import (
    UploadChatbotConversationSerializer,
    UploadChatbotMessageSerializer
)

logger = logging.getLogger(__name__)


class UploadChatbotView(View):
    """Main view for upload chatbot functionality"""
    
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
            
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                conversation = None
                conversation_history = []
            else:
                conversation = self._get_or_create_conversation(user, session_id, user_message)
                conversation_history = self._get_conversation_history(conversation)
            
            # Get upload chatbot service
            upload_chatbot_service = get_upload_chatbot_service()
            
            # Check if service is available
            if not upload_chatbot_service.is_available():
                return JsonResponse({
                    'success': False,
                    'error': 'AI service not available',
                    'message': 'OpenAI API key not configured or service unavailable'
                }, status=503)
            
            # Generate AI response
            ai_response = upload_chatbot_service.generate_ai_response(
                user_message=user_message,
                user=request.user,
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
                user_msg = UploadChatbotMessage.objects.create(
                    conversation=conversation,
                    role='user',
                    content=user_message
                )
                
                # Save AI response
                ai_msg = UploadChatbotMessage.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=ai_response['response'],
                    metadata={
                        'usage': ai_response.get('usage'),
                        'model': ai_response.get('model'),
                        'timestamp': ai_response.get('timestamp')
                    }
                )
                
                # Update conversation
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
        except Exception as e:
            logger.error(f"Error in upload chatbot: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)
    
    def _get_or_create_conversation(self, user, session_id, user_message):
        """Get existing conversation or create new one"""
        if session_id:
            try:
                conversation = UploadChatbotConversation.objects.get(
                    session_id=session_id,
                    user=user,
                    status='active'
                )
                return conversation
            except UploadChatbotConversation.DoesNotExist:
                pass
        
        # Create new conversation
        new_session_id = str(uuid.uuid4())
        title = user_message[:50] + "..." if len(user_message) > 50 else user_message
        
        conversation = UploadChatbotConversation.objects.create(
            user=user,
            session_id=new_session_id,
            title=title,
            status='active'
        )
        
        return conversation
    
    def _get_conversation_history(self, conversation):
        """Get conversation history for context"""
        messages = conversation.messages.all().order_by('timestamp')[-10:]  
        
        history = []
        for msg in messages:
            history.append({
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            })
        
        return history


@csrf_exempt
@require_http_methods(["POST", "GET"])
def upload_chatbot_quick_suggestions(request):
    """Get quick suggestions for upload chatbot"""
    try:
        upload_chatbot_service = get_upload_chatbot_service()
        
        if not upload_chatbot_service.is_available():
            return JsonResponse({
                'success': False,
                'error': 'AI service not available'
            }, status=503)
        
        suggestions = upload_chatbot_service.get_quick_suggestions()
        
        return JsonResponse({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error getting quick suggestions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get suggestions'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def upload_chatbot_conversations(request):
    """Get user's upload chatbot conversations"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        conversations = UploadChatbotConversation.objects.filter(
            user=request.user,
            status='active'
        ).order_by('-last_activity')[:20]
        
        serializer = UploadChatbotConversationSerializer(conversations, many=True)
        
        return JsonResponse({
            'success': True,
            'conversations': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get conversations'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def upload_chatbot_conversation_detail(request, conversation_id):
    """Get specific conversation with messages"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        conversation = UploadChatbotConversation.objects.get(
            id=conversation_id,
            user=request.user,
            status='active'
        )
        
        messages = conversation.messages.all().order_by('timestamp')
        
        conversation_data = UploadChatbotConversationSerializer(conversation).data
        messages_data = UploadChatbotMessageSerializer(messages, many=True).data
        
        return JsonResponse({
            'success': True,
            'conversation': conversation_data,
            'messages': messages_data
        })
        
    except UploadChatbotConversation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Conversation not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting conversation detail: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get conversation'
        }, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def upload_chatbot_delete_conversation(request, conversation_id):
    """Delete a conversation"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        conversation = UploadChatbotConversation.objects.get(
            id=conversation_id,
            user=request.user,
            status='active'
        )
        
        conversation.status = 'deleted'
        conversation.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Conversation deleted successfully'
        })
        
    except UploadChatbotConversation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Conversation not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to delete conversation'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def upload_chatbot_status(request):
    """Get upload chatbot service status"""
    try:
        upload_chatbot_service = get_upload_chatbot_service()
        
        is_available = upload_chatbot_service.is_available()
        
        return JsonResponse({
            'success': True,
            'available': is_available,
            'message': 'Service is available' if is_available else 'Service is not available'
        })
        
    except Exception as e:
        logger.error(f"Error checking service status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to check service status'
        }, status=500)
