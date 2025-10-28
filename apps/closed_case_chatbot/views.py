from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db.models import Q
import openai
from .models import ClosedCaseChatbot, ClosedCaseChatbotMessage


def generate_related_suggestions(user_message, ai_response):
    """
    Generate 3 related suggestions based on the user's question and AI response
    """
    all_suggestions = [
        "What are closed cases?",
        "Show me trends in my closed cases",
        "What are the common reasons for case closures?",
        "How many closed cases do I have?",
        "What is the closed case analysis?",
        "Show me closed case statistics",
        "What are the closed case patterns?",
        "How can I improve case closure rates?",
        "What insights do closed cases provide?",
        "Show me closed case performance metrics",
        "What are the closed case trends?",
        "How do closed cases affect renewal rates?",
        "What is the closed case summary?",
        "Show me closed case details",
        "What are the closed case categories?",
        "How can I reduce case closures?",
        "What is the closed case impact?",
        "Show me closed case reports",
        "What are the closed case insights?",
        "How do closed cases compare to active cases?"
    ]
    
    message_lower = user_message.lower()
    
    if 'what is' in message_lower or 'explain' in message_lower or 'define' in message_lower:
        context_suggestions = [
            "Show me trends in my closed cases",
            "What are the common reasons for case closures?",
            "How many closed cases do I have?"
        ]
    
    elif 'trend' in message_lower or 'pattern' in message_lower or 'analysis' in message_lower:
        context_suggestions = [
            "What are the common reasons for case closures?",
            "Show me closed case statistics",
            "What insights do closed cases provide?"
        ]
    
    elif 'reason' in message_lower or 'why' in message_lower or 'cause' in message_lower:
        context_suggestions = [
            "Show me trends in my closed cases",
            "What are the closed case patterns?",
            "How can I improve case closure rates?"
        ]
    
    elif 'how many' in message_lower or 'count' in message_lower or 'total' in message_lower:
        context_suggestions = [
            "Show me closed case statistics",
            "What is the closed case analysis?",
            "Show me closed case performance metrics"
        ]
    
    elif 'statistic' in message_lower or 'metric' in message_lower or 'performance' in message_lower:
        context_suggestions = [
            "What are the closed case trends?",
            "Show me closed case reports",
            "What insights do closed cases provide?"
        ]
    
    elif 'improve' in message_lower or 'reduce' in message_lower or 'optimize' in message_lower:
        context_suggestions = [
            "What are the common reasons for case closures?",
            "How can I improve case closure rates?",
            "What insights do closed cases provide?"
        ]
    
    elif 'insight' in message_lower or 'impact' in message_lower or 'effect' in message_lower:
        context_suggestions = [
            "Show me closed case statistics",
            "What are the closed case patterns?",
            "How do closed cases affect renewal rates?"
        ]
    
    else:
        context_suggestions = [
            "Show me trends in my closed cases",
            "What are the common reasons for case closures?",
            "How many closed cases do I have?"
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
def get_suggestions(request):
    """
    Get quick suggestions for closed case chatbot
    """
    suggestions = [
        "Analyze my current renewal portfolio performance",
        "What strategies can improve my renewal rates?",
        "How can I optimize my digital channel performance?",
        "What are the key bottlenecks in my renewal process?",
        "Provide insights on my premium collection efficiency",
        "How can I reduce customer churn this quarter?",
        "What predictive insights do you see in my data?",
        "Show me trends in my closed cases",
        "What are the common reasons for case closures?",
        "How can I improve customer satisfaction scores?"
    ]
    
    return Response({
        'suggestions': suggestions,
        'message': 'Quick suggestions for closed case analysis'
    })


def get_closed_cases_context():
    """
    Get context data from closed cases for AI response
    """
    try:
        from apps.closed_cases.models import ClosedCase
        
        recent_cases = ClosedCase.objects.all()[:10]
        
        context_data = {
            'total_closed_cases': ClosedCase.objects.count(),
            'recent_cases': []
        }
        
        for case in recent_cases:
            context_data['recent_cases'].append({
                'case_id': getattr(case, 'case_id', 'N/A'),
                'customer_name': getattr(case, 'customer_name', 'N/A'),
                'policy_number': getattr(case, 'policy_number', 'N/A'),
                'product_name': getattr(case, 'product_name', 'N/A'),
                'category': getattr(case, 'category', 'N/A'),
                'closed_date': getattr(case, 'closed_date', 'N/A'),
                'reason': getattr(case, 'reason', 'N/A')
            })
        
        return context_data
    except Exception as e:
        return {
            'total_closed_cases': 0,
            'recent_cases': [],
            'error': str(e)
        }


def is_case_related_question(message):
    """
    Check if the question is related to closed cases
    """
    case_keywords = [
        'case', 'closed', 'policy', 'renewal', 'customer', 'premium', 
        'claim', 'insurance', 'portfolio', 'churn', 'retention', 'collection',
        'bottleneck', 'process', 'efficiency', 'performance', 'strategy',
        'trend', 'analysis', 'insight', 'data', 'report', 'metric'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in case_keywords)


def generate_ai_response(user_message, context_data):
    """
    Generate AI response using OpenAI API
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        context_text = f"""
        You are a helpful AI assistant for an insurance renewal management system. 
        You specialize in analyzing closed cases data and providing insights.
        
        Current closed cases context:
        - Total closed cases: {context_data.get('total_closed_cases', 0)}
        - Recent cases: {len(context_data.get('recent_cases', []))}
        
        User question: {user_message}
        
        Please provide a helpful, professional response based on the context provided.
        If the question is not related to closed cases or insurance, politely redirect them.
        Keep responses concise but informative.
        """
        
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert insurance renewal management assistant specializing in closed cases analysis."},
                {"role": "user", "content": context_text}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"I apologize, but I'm currently unable to process your request due to a technical issue. Please try again later."


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_request_get_response(request):
    """
    Send a request to chatbot and get AI response
    """
    user_message = request.data.get('message', '')
    
    if not user_message:
        return Response({
            'error': 'Message is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not is_case_related_question(user_message):
        return Response({
            'response': "I'm sorry, but I'm specifically designed to help with closed cases analysis and insurance renewal management. Please ask me questions related to:\n\n• Closed cases analysis\n• Renewal strategies\n• Customer retention\n• Policy performance\n• Process optimization\n• Portfolio insights\n\nHow can I assist you with your closed cases today?"
        }, status=status.HTTP_200_OK)
    
    chatbot_session, created = ClosedCaseChatbot.objects.get_or_create(
        case_id=request.data.get('case_id', 'DEFAULT'),
        defaults={
            'customer_name': request.data.get('customer_name', 'Anonymous'),
            'policy_number': request.data.get('policy_number', 'N/A'),
            'product_name': request.data.get('product_name', 'Insurance'),
            'category': request.data.get('category', 'General'),
            'mobile_number': request.data.get('mobile_number', 'N/A'),
            'language': request.data.get('language', 'English'),
            'profile_type': request.data.get('profile_type', 'Normal'),
            'chatbot_session_id': f"session_{request.user.id}_{request.data.get('case_id', 'default')}",
            'is_active': True
        }
    )
    
    user_msg = ClosedCaseChatbotMessage.objects.create(
        chatbot_session=chatbot_session,
        message_type='user',
        content=user_message
    )
    
    context_data = get_closed_cases_context()
    
    ai_response = generate_ai_response(user_message, context_data)
    
    ai_msg = ClosedCaseChatbotMessage.objects.create(
        chatbot_session=chatbot_session,
        message_type='bot',
        content=ai_response
    )
    
    chatbot_session.interaction_count += 1
    chatbot_session.save()
    
    related_suggestions = generate_related_suggestions(user_message, ai_response)
    
    return Response({
        'response': ai_response,
        'suggestions': related_suggestions
    }, status=status.HTTP_200_OK)
