import uuid
from datetime import datetime, timedelta
from django.db.models import Q, Count, Avg
from django.utils import timezone
from .models import ClosedCaseChatbot, ClosedCaseChatbotMessage, ClosedCaseChatbotAnalytics
class ClosedCaseChatbotService:
    @staticmethod
    def create_chatbot_session(case_data):
        """
        Create a new chatbot session for a closed case
        """
        session_id = f"chatbot_{uuid.uuid4().hex[:12]}"
        
        chatbot_data = {
            'case_id': case_data.get('case_id'),
            'customer_name': case_data.get('customer_name'),
            'policy_number': case_data.get('policy_number'),
            'product_name': case_data.get('product_name'),
            'category': case_data.get('category'),
            'mobile_number': case_data.get('mobile_number'),
            'language': case_data.get('language', 'English'),
            'profile_type': case_data.get('profile_type', 'Normal'),
            'chatbot_session_id': session_id,
            'is_active': True
        }
        
        chatbot = ClosedCaseChatbot.objects.create(**chatbot_data)
        return chatbot
    
    @staticmethod
    def get_chatbot_by_case_id(case_id):
        try:
            return ClosedCaseChatbot.objects.get(case_id=case_id)
        except ClosedCaseChatbot.DoesNotExist:
            return None
    
    @staticmethod
    def get_chatbot_by_session_id(session_id):
       
        try:
            return ClosedCaseChatbot.objects.get(chatbot_session_id=session_id)
        except ClosedCaseChatbot.DoesNotExist:
            return None
    
    @staticmethod
    def send_message(chatbot_session, message_type, content, is_helpful=None):
       
        message_data = {
            'chatbot_session': chatbot_session,
            'message_type': message_type,
            'content': content,
            'is_helpful': is_helpful
        }
        
        message = ClosedCaseChatbotMessage.objects.create(**message_data)
        
        chatbot_session.last_interaction = timezone.now()
        chatbot_session.save()
        
        return message
    
    @staticmethod
    def get_conversation_history(chatbot_session, limit=None):
       
        messages = chatbot_session.messages.all().order_by('timestamp')
        
        if limit:
            messages = messages[:limit]
        
        return messages
    
    @staticmethod
    def deactivate_chatbot(chatbot_session):
        
        chatbot_session.is_active = False
        chatbot_session.save()
        return chatbot_session
    
    @staticmethod
    def reactivate_chatbot(chatbot_session):
       
        chatbot_session.is_active = True
        chatbot_session.save()
        return chatbot_session
    
    @staticmethod
    def search_closed_cases(search_terms):
       
        if not search_terms:
            return ClosedCaseChatbot.objects.none()
        
        terms = [term.strip() for term in search_terms.split(',')]
        
        q_objects = Q()
        for term in terms:
            q_objects |= (
                Q(case_id__icontains=term) |
                Q(customer_name__icontains=term) |
                Q(policy_number__icontains=term) |
                Q(mobile_number__icontains=term)
            )
        
        return ClosedCaseChatbot.objects.filter(q_objects)
    
    @staticmethod
    def get_active_chatbots():
        
        return ClosedCaseChatbot.objects.filter(is_active=True)
    
    @staticmethod
    def get_inactive_chatbots():
        
        return ClosedCaseChatbot.objects.filter(is_active=False)
    
    @staticmethod
    def get_chatbots_by_category(category):
       
        return ClosedCaseChatbot.objects.filter(category__icontains=category)
    
    @staticmethod
    def get_chatbots_by_profile_type(profile_type):
        
        return ClosedCaseChatbot.objects.filter(profile_type=profile_type)

class ClosedCaseChatbotAnalyticsService:
    @staticmethod
    def record_metric(chatbot_session, metric_name, metric_value, metric_date=None):
       
        if metric_date is None:
            metric_date = timezone.now().date()
        
        analytics_data = {
            'chatbot_session': chatbot_session,
            'metric_name': metric_name,
            'metric_value': metric_value,
            'metric_date': metric_date
        }
        
        analytics = ClosedCaseChatbotAnalytics.objects.create(**analytics_data)
        return analytics
    
    @staticmethod
    def get_session_analytics(chatbot_session):
       
        return chatbot_session.analytics.all().order_by('-metric_date')
    
    @staticmethod
    def get_metric_summary(metric_name, start_date=None, end_date=None):
       
        queryset = ClosedCaseChatbotAnalytics.objects.filter(metric_name=metric_name)
        
        if start_date:
            queryset = queryset.filter(metric_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(metric_date__lte=end_date)
        
        return {
            'count': queryset.count(),
            'average': queryset.aggregate(avg=Avg('metric_value'))['avg'] or 0,
            'total': queryset.aggregate(total=Count('id'))['total'] or 0
        }
    
    @staticmethod
    def get_daily_interaction_stats(days=30):
       
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        stats = []
        current_date = start_date
        
        while current_date <= end_date:
            count = ClosedCaseChatbotMessage.objects.filter(
                timestamp__date=current_date
            ).count()
            
            stats.append({
                'date': current_date,
                'interaction_count': count
            })
            
            current_date += timedelta(days=1)
        
        return stats
    
    @staticmethod
    def get_category_wise_stats():
        return ClosedCaseChatbot.objects.values('category').annotate(
            total_cases=Count('id'),
            active_cases=Count('id', filter=Q(is_active=True)),
            avg_interactions=Avg('interaction_count')
        ).order_by('-total_cases')
    
    @staticmethod
    def get_profile_type_stats():
        return ClosedCaseChatbot.objects.values('profile_type').annotate(
            total_cases=Count('id'),
            active_cases=Count('id', filter=Q(is_active=True)),
            avg_interactions=Avg('interaction_count')
        ).order_by('-total_cases')
    
    @staticmethod
    def get_language_wise_stats():
        return ClosedCaseChatbot.objects.values('language').annotate(
            total_cases=Count('id'),
            active_cases=Count('id', filter=Q(is_active=True)),
            avg_interactions=Avg('interaction_count')
        ).order_by('-total_cases')


class ClosedCaseChatbotMessageService:
    @staticmethod
    def get_recent_messages(chatbot_session, limit=10):
        """
        Get recent messages for a chatbot session
        """
        return chatbot_session.messages.all().order_by('-timestamp')[:limit]
    
    @staticmethod
    def get_messages_by_type(chatbot_session, message_type):
        """
        Get messages of a specific type for a chatbot session
        """
        return chatbot_session.messages.filter(message_type=message_type)
    
    @staticmethod
    def update_message_feedback(message_id, is_helpful):
        """
        Update feedback for a specific message
        """
        try:
            message = ClosedCaseChatbotMessage.objects.get(id=message_id)
            message.is_helpful = is_helpful
            message.save()
            return message
        except ClosedCaseChatbotMessage.DoesNotExist:
            return None
    
    @staticmethod
    def get_helpful_messages_count(chatbot_session):
        """
        Get count of helpful messages for a chatbot session
        """
        return chatbot_session.messages.filter(is_helpful=True).count()
    
    @staticmethod
    def get_unhelpful_messages_count(chatbot_session):
        """
        Get count of unhelpful messages for a chatbot session
        """
        return chatbot_session.messages.filter(is_helpful=False).count()
