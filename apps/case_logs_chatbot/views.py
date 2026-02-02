from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db.models import Q
from .models import CaseLogsChatbot, CaseLogsChatbotMessage


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_suggestions(request):
    suggestions = [
        "Show me my renewal case logs",
        "What is the status of my renewal case?",
        "Tell me about my case history",
        "What are the recent activities in my case?",
        "Show me case details by Case ID",
        "Show me case details by Policy Number",
        "What is the renewal amount for my case?",
        "What is the payment status of my case?",
        "Who is assigned to my case?",
        "Tell me about case timeline",
        "What are the case updates?",
        "Show me case comments and notes",
        "What is the case resolution?",
        "Tell me about case assignments",
        "What are the case milestones?",
        "Show me case attachments",
        "What is the case escalation status?",
        "What is my renewal case priority?",
        "Show me customer information for my case",
        "Tell me about policy details for my case"
    ]
    
    return Response({
        'suggestions': suggestions,
        'message': 'Quick suggestions for case logs analysis'
    })

def get_case_logs_context(case_id=None, policy_id=None, user=None):
    try:
        context_data = {
            'case_info': {},
            'case_logs': [],
            'case_history': [],
            'case_comments': [],
            'case_attachments': []
        }
        
        try:
            from apps.renewals.models import RenewalCase
            if case_id:
                renewal_cases = RenewalCase.objects.filter(case_number=case_id).order_by('-created_at')[:10]
                if renewal_cases.exists():
                    renewal_case = renewal_cases.first()
                    context_data['case_info'] = {
                        'case_number': getattr(renewal_case, 'case_number', 'N/A'),
                        'policy_id': getattr(renewal_case.policy, 'policy_id', 'N/A') if renewal_case.policy else 'N/A',
                        'customer_id': getattr(renewal_case.customer, 'customer_id', 'N/A') if renewal_case.customer else 'N/A',
                        'customer_name': getattr(renewal_case.customer, 'full_name', 'N/A') if renewal_case.customer else 'N/A',
                        'case_type': 'Renewal',
                        'status': getattr(renewal_case, 'status', 'N/A'),
                        'priority': getattr(renewal_case, 'priority', 'N/A'),
                        'renewal_amount': getattr(renewal_case, 'renewal_amount', 'N/A'),
                        'payment_status': getattr(renewal_case, 'payment_status', 'N/A'),
                        'assigned_to': getattr(renewal_case.assigned_to, 'username', 'N/A') if renewal_case.assigned_to else 'N/A',
                        'created_at': getattr(renewal_case, 'created_at', 'N/A'),
                        'updated_at': getattr(renewal_case, 'updated_at', 'N/A'),
                        'notes': getattr(renewal_case, 'notes', 'N/A')
                    }
                    
                    for case in renewal_cases:
                        context_data['case_logs'].append({
                            'case_number': getattr(case, 'case_number', 'N/A'),
                            'status': getattr(case, 'status', 'N/A'),
                            'renewal_amount': getattr(case, 'renewal_amount', 'N/A'),
                            'payment_status': getattr(case, 'payment_status', 'N/A'),
                            'assigned_to': getattr(case.assigned_to, 'username', 'N/A') if case.assigned_to else 'N/A',
                            'timestamp': getattr(case, 'created_at', 'N/A'),
                            'notes': getattr(case, 'notes', 'N/A')
                        })
                else:
                    context_data['no_case_found'] = True
                    context_data['case_id'] = case_id
            elif policy_id:
                renewal_cases = RenewalCase.objects.filter(policy__policy_id=policy_id).order_by('-created_at')[:10]
                if renewal_cases.exists():
                    renewal_case = renewal_cases.first()
                    context_data['case_info'] = {
                        'case_number': getattr(renewal_case, 'case_number', 'N/A'),
                        'policy_id': getattr(renewal_case.policy, 'policy_id', 'N/A') if renewal_case.policy else 'N/A',
                        'customer_id': getattr(renewal_case.customer, 'customer_id', 'N/A') if renewal_case.customer else 'N/A',
                        'customer_name': getattr(renewal_case.customer, 'full_name', 'N/A') if renewal_case.customer else 'N/A',
                        'case_type': 'Renewal',
                        'status': getattr(renewal_case, 'status', 'N/A'),
                        'priority': getattr(renewal_case, 'priority', 'N/A'),
                        'renewal_amount': getattr(renewal_case, 'renewal_amount', 'N/A'),
                        'payment_status': getattr(renewal_case, 'payment_status', 'N/A'),
                        'assigned_to': getattr(renewal_case.assigned_to, 'username', 'N/A') if renewal_case.assigned_to else 'N/A',
                        'created_at': getattr(renewal_case, 'created_at', 'N/A'),
                        'updated_at': getattr(renewal_case, 'updated_at', 'N/A'),
                        'notes': getattr(renewal_case, 'notes', 'N/A')
                    }
                    
                    for case in renewal_cases:
                        context_data['case_logs'].append({
                            'case_number': getattr(case, 'case_number', 'N/A'),
                            'status': getattr(case, 'status', 'N/A'),
                            'renewal_amount': getattr(case, 'renewal_amount', 'N/A'),
                            'payment_status': getattr(case, 'payment_status', 'N/A'),
                            'assigned_to': getattr(case.assigned_to, 'username', 'N/A') if case.assigned_to else 'N/A',
                            'timestamp': getattr(case, 'created_at', 'N/A'),
                            'notes': getattr(case, 'notes', 'N/A')
                        })
                else:
                    context_data['no_case_found'] = True
                    context_data['policy_id'] = policy_id
            else:
                renewal_cases = RenewalCase.objects.all()[:10]
                for case in renewal_cases:
                    context_data['case_logs'].append({
                        'case_number': getattr(case, 'case_number', 'N/A'),
                        'policy_id': getattr(case.policy, 'policy_id', 'N/A') if case.policy else 'N/A',
                        'customer_id': getattr(case.customer, 'customer_id', 'N/A') if case.customer else 'N/A',
                        'status': getattr(case, 'status', 'N/A'),
                        'renewal_amount': getattr(case, 'renewal_amount', 'N/A'),
                        'payment_status': getattr(case, 'payment_status', 'N/A'),
                        'assigned_to': getattr(case.assigned_to, 'username', 'N/A') if case.assigned_to else 'N/A',
                        'timestamp': getattr(case, 'created_at', 'N/A'),
                        'notes': getattr(case, 'notes', 'N/A')
                    })
        except Exception:
            pass
        
        try:
            from apps.case_history.models import CaseHistory
            if case_id:
                case_histories = CaseHistory.objects.filter(case_id=case_id).order_by('-created_at')[:5]
                for history in case_histories:
                    context_data['case_history'].append({
                        'history_id': getattr(history, 'id', 'N/A'),
                        'action': getattr(history, 'action', 'N/A'),
                        'description': getattr(history, 'description', 'N/A'),
                        'user': getattr(history, 'user', 'N/A'),
                        'timestamp': getattr(history, 'created_at', 'N/A')
                    })
        except Exception:
            pass
        
        try:
            from apps.case_history.models import CaseComment
            if case_id:
                case_comments = CaseComment.objects.filter(case_id=case_id).order_by('-created_at')[:5]
                for comment in case_comments:
                    context_data['case_comments'].append({
                        'comment_id': getattr(comment, 'id', 'N/A'),
                        'comment': getattr(comment, 'comment', 'N/A'),
                        'user': getattr(comment, 'user', 'N/A'),
                        'timestamp': getattr(comment, 'created_at', 'N/A')
                    })
        except Exception:
            pass
        
        return context_data
        
    except Exception as e:
        return {
            'case_info': {},
            'case_logs': [],
            'case_history': [],
            'case_comments': [],
            'case_attachments': [],
            'error': str(e)
        }

def is_case_logs_related_question(message):
    case_logs_keywords = [
        'case', 'log', 'logs', 'policy', 'status', 'history', 'activity',
        'timeline', 'update', 'comment', 'note', 'attachment', 'resolution',
        'assignment', 'milestone', 'escalation', 'priority', 'type',
        'customer', 'details', 'information', 'tracking', 'progress'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in case_logs_keywords)


def generate_related_suggestions(user_message, context_data, ai_response):
    suggestions = []
    
    case_info = context_data.get('case_info', {})
    case_number = case_info.get('case_number', '')
    status = case_info.get('status', '')
    payment_status = case_info.get('payment_status', '')
    
    message_lower = user_message.lower()
    
    if 'case logs' in message_lower or 'what is' in message_lower:
        if case_number:
            suggestions = [
                f"What is the current status of case {case_number}?",
                f"Who is assigned to case {case_number}?",
                f"What is the renewal amount for case {case_number}?"
            ]
        else:
            suggestions = [
                "Show me my case logs",
                "What is the status of my renewal case?",
                "Tell me about my case history"
            ]
    
    elif 'status' in message_lower:
        if case_number:
            suggestions = [
                f"What is the payment status of case {case_number}?",
                f"Who is assigned to case {case_number}?",
                f"What is the renewal amount for case {case_number}?"
            ]
        else:
            suggestions = [
                "What is the payment status of my case?",
                "Who is assigned to my case?",
                "What is the renewal amount for my case?"
            ]
    
    elif 'payment' in message_lower:
        if case_number:
            suggestions = [
                f"What is the current status of case {case_number}?",
                f"When was the payment made for case {case_number}?",
                f"What is the renewal amount for case {case_number}?"
            ]
        else:
            suggestions = [
                "What is the current status of my case?",
                "When was the payment made?",
                "What is the renewal amount?"
            ]
    
    elif 'amount' in message_lower or 'renewal' in message_lower:
        if case_number:
            suggestions = [
                f"What is the payment status of case {case_number}?",
                f"What is the current status of case {case_number}?",
                f"Who is assigned to case {case_number}?"
            ]
        else:
            suggestions = [
                "What is the payment status of my case?",
                "What is the current status of my case?",
                "Who is assigned to my case?"
            ]
    
    elif 'assigned' in message_lower or 'who' in message_lower:
        if case_number:
            suggestions = [
                f"What is the current status of case {case_number}?",
                f"What is the renewal amount for case {case_number}?",
                f"What are the notes for case {case_number}?"
            ]
        else:
            suggestions = [
                "What is the current status of my case?",
                "What is the renewal amount?",
                "What are the case notes?"
            ]
    
    elif 'history' in message_lower or 'timeline' in message_lower:
        if case_number:
            suggestions = [
                f"What is the current status of case {case_number}?",
                f"What are the recent updates for case {case_number}?",
                f"What is the renewal amount for case {case_number}?"
            ]
        else:
            suggestions = [
                "What is the current status of my case?",
                "What are the recent updates?",
                "What is the renewal amount?"
            ]
    
    else:
        if case_number:
            suggestions = [
                f"What is the current status of case {case_number}?",
                f"What is the payment status of case {case_number}?",
                f"Who is assigned to case {case_number}?"
            ]
        else:
            suggestions = [
                "What is the status of my renewal case?",
                "What is the payment status of my case?",
                "Who is assigned to my case?"
            ]
    
    return suggestions[:3]


def generate_ai_response(user_message, context_data):
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        context_summary = []
        
        if context_data.get('case_info'):
            case_info = context_data['case_info']
            context_summary.append(f"Case: {case_info.get('case_number', 'N/A')} (Status: {case_info.get('status', 'N/A')})")
            context_summary.append(f"Customer: {case_info.get('customer_name', 'N/A')} (ID: {case_info.get('customer_id', 'N/A')})")
            context_summary.append(f"Policy: {case_info.get('policy_id', 'N/A')}")
            context_summary.append(f"Renewal Amount: {case_info.get('renewal_amount', 'N/A')}")
            context_summary.append(f"Payment Status: {case_info.get('payment_status', 'N/A')}")
            context_summary.append(f"Assigned To: {case_info.get('assigned_to', 'N/A')}")
            if case_info.get('notes'):
                context_summary.append(f"Notes: {case_info.get('notes', 'N/A')}")
        
        if context_data.get('case_logs'):
            context_summary.append(f"Case Logs: {len(context_data['case_logs'])} log entries")
            if context_data['case_logs']:
                sample_log = context_data['case_logs'][0]
                context_summary.append(f"Latest Status: {sample_log.get('status', 'N/A')} - Amount: {sample_log.get('renewal_amount', 'N/A')}")
        
        if context_data.get('case_history'):
            context_summary.append(f"Case History: {len(context_data['case_history'])} history entries")
        
        if context_data.get('case_comments'):
            context_summary.append(f"Case Comments: {len(context_data['case_comments'])} comments")
        
        if context_data.get('no_case_found'):
            context_summary.append(f"No case found for {'Case ID' if context_data.get('case_id') else 'Policy ID'}: {context_data.get('case_id') or context_data.get('policy_id', 'N/A')}")
        
        context_text = f"""
        You are a helpful AI assistant for a case logs management system specializing in renewal cases. 
        You analyze renewal case data, case status, payment information, and case-related activities.
        
        Current renewal case context:
        {chr(10).join(context_summary) if context_summary else "General renewal case data available"}
        
        User question: {user_message}
        
        Please provide a helpful, professional response based on the renewal case context provided.
        If you have specific renewal case data, use it to provide detailed information about:
        - Case status and progress
        - Renewal amounts and payment status
        - Customer and policy information
        - Assignment details
        - Case timeline and activities
        
        If no specific case is found, inform them politely that no case information is available for the provided Case ID or Policy Number and suggest they verify the details.
        If you have specific data, use it to give detailed, accurate information. If not, provide general guidance about renewal case management.
        Keep responses concise but informative and always be helpful.
        """
        
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert renewal case management assistant specializing in renewal case analysis, status tracking, and payment management."},
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
    user_message = request.data.get('message', '')
    
    if not user_message:
        return Response({
            'error': 'Message is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not is_case_logs_related_question(user_message):
        return Response({
            'response': "I'm sorry, but I'm specifically designed to help with case logs analysis and case management. Please ask me questions related to:\n\n• Case logs and activities\n• Case status and history\n• Case details by Case ID or Policy Number\n• Case timeline and updates\n• Case comments and notes\n• Case assignments and milestones\n\nHow can I assist you with your case logs today?"
        }, status=status.HTTP_200_OK)
    
    chatbot_session, created = CaseLogsChatbot.objects.get_or_create(
        case_id=request.data.get('case_id', 'DEFAULT'),
        defaults={
            'policy_id': request.data.get('policy_id', 'N/A'),
            'customer_id': request.data.get('customer_id', 'N/A'),
            'case_type': request.data.get('case_type', 'General'),
            'case_status': request.data.get('case_status', 'Open'),
            'priority': request.data.get('priority', 'Medium'),
            'chatbot_session_id': f"session_{request.user.id}_{request.data.get('case_id', 'default')}",
            'is_active': True
        }
    )
    
    user_msg = CaseLogsChatbotMessage.objects.create(
        chatbot_session=chatbot_session,
        message_type='user',
        content=user_message
    )
    
    context_data = get_case_logs_context(
        case_id=request.data.get('case_id'),
        policy_id=request.data.get('policy_id'),
        user=request.user
    )
    
    print(f"DEBUG: Context data fetched: {context_data}")
    
    ai_response = generate_ai_response(user_message, context_data)
    
    ai_msg = CaseLogsChatbotMessage.objects.create(
        chatbot_session=chatbot_session,
        message_type='bot',
        content=ai_response
    )
    
    chatbot_session.interaction_count += 1
    chatbot_session.save()
    
    related_suggestions = generate_related_suggestions(user_message, context_data, ai_response)
    
    return Response({
        'response': ai_response,
        'suggestions': related_suggestions
    }, status=status.HTTP_200_OK)