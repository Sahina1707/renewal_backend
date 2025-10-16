import logging
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from django.contrib.auth import get_user_model

# OpenAI imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

from apps.campaigns.models import Campaign, CampaignRecipient
from apps.uploads.models import UploadFile
from apps.channels.models import Channel
from apps.customer_communication_preferences.models import CommunicationLog

User = get_user_model()
logger = logging.getLogger(__name__)


class UploadChatbotService:
    """Service for handling upload and campaign-related chatbot queries"""
    
    def __init__(self):
        self.openai_client = None
        self._initialize_openai()
    
    def _initialize_openai(self):
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not available")
            return False
        
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            logger.warning("OpenAI API key not configured")
            return False
        
        try:
            self.openai_client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        return (
            OPENAI_AVAILABLE and 
            self.openai_client is not None and 
            bool(getattr(settings, 'OPENAI_API_KEY', ''))
        )
    
    def get_upload_campaign_data(self) -> Dict[str, Any]:
        """Get comprehensive data for upload and campaign analysis"""
        try:
            campaigns = Campaign.objects.filter(is_deleted=False)
            
            campaign_stats = {
                'total_campaigns': campaigns.count(),
                'active_campaigns': campaigns.filter(status='active').count(),
                'completed_campaigns': campaigns.filter(status='completed').count(),
                'scheduled_campaigns': campaigns.filter(status='scheduled').count(),
                'failed_campaigns': campaigns.filter(status='failed').count(),
            }
            
            campaign_performance = campaigns.values('campaign_type__name').annotate(
                count=Count('id'),
                total_targets=Sum('target_count'),
                avg_targets=Avg('target_count')
            )
            
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            
            recent_campaigns = campaigns.filter(
                created_at__gte=thirty_days_ago
            ).values('status').annotate(
                count=Count('id')
            )
            
            campaign_recipients = CampaignRecipient.objects.filter(
                campaign__is_deleted=False
            )
            
            recipient_stats = {
                'total_recipients': campaign_recipients.count(),
                'email_sent': campaign_recipients.filter(email_status='sent').count(),
                'email_delivered': campaign_recipients.filter(email_status='delivered').count(),
                'email_opened': campaign_recipients.filter(email_engagement='opened').count(),
                'email_clicked': campaign_recipients.filter(email_engagement='clicked').count(),
                'whatsapp_sent': campaign_recipients.filter(whatsapp_status='sent').count(),
                'whatsapp_delivered': campaign_recipients.filter(whatsapp_status='delivered').count(),
                'sms_sent': campaign_recipients.filter(sms_status='sent').count(),
                'sms_delivered': campaign_recipients.filter(sms_status='delivered').count(),
            }
            
            upload_files = UploadFile.objects.filter(is_deleted=False)
            
            upload_stats = {
                'total_uploads': upload_files.count(),
                'successful_uploads': upload_files.filter(status='completed').count(),
                'failed_uploads': upload_files.filter(status='failed').count(),
                'processing_uploads': upload_files.filter(status='processing').count(),
            }
            
            recent_uploads = upload_files.filter(
                created_at__gte=thirty_days_ago
            ).values('status').annotate(
                count=Count('id'),
                total_records=Sum('total_records'),
                successful_records=Sum('successful_records'),
                failed_records=Sum('failed_records')
            )
            
            channel_performance = Channel.objects.filter(
                is_deleted=False
            ).values(
                'name', 'channel_type', 'status'
            ).annotate(
                total_channels=Count('id')
            )
            
            communication_stats = CommunicationLog.objects.filter(
                communication_date__gte=thirty_days_ago
            ).values('channel').annotate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])),
                success_rate=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])) * 100.0 / Count('id')
            )
            
            return {
                'campaign_stats': campaign_stats,
                'campaign_performance': list(campaign_performance),
                'recent_campaigns': list(recent_campaigns),
                'recipient_stats': recipient_stats,
                'upload_stats': upload_stats,
                'recent_uploads': list(recent_uploads),
                'channel_performance': list(channel_performance),
                'communication_stats': list(communication_stats),
                'timestamp': timezone.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error fetching upload campaign data: {str(e)}")
            return {}
    
    def generate_ai_response(self, user_message: str, context_data: Dict[str, Any] = None, user=None, conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not available',
                'message': 'OpenAI API key not configured or service unavailable'
            }
        
        try:
            query_type = self._classify_query(user_message)
            
            if query_type == 'non_campaign':
                return {
                    'success': True,
                    'response': 'Sorry, I can only help with campaign-related questions. Please ask me about campaigns, uploads, or communication management.',
                    'model': 'direct-response',
                    'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
                    'timestamp': timezone.now().isoformat()
                }
            
            dashboard_data = self.get_upload_campaign_data()
            specialized_data = self._get_specialized_data(query_type, user_message)
            dashboard_data.update(specialized_data)
            
            system_prompt = self._create_system_prompt(dashboard_data, user, query_type)
            
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                for msg in conversation_history:
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            messages.append({"role": "user", "content": user_message})
            
            response = self.openai_client.chat.completions.create(
                model=getattr(settings, 'OPENAI_MODEL', 'gpt-4'),
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            ai_response = response.choices[0].message.content
            
            return {
                'success': True,
                'response': ai_response,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                } if response.usage else None,
                'model': response.model,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to generate AI response'
            }
    
    def _classify_query(self, user_message: str) -> str:
        """Classify the type of query to determine what data to fetch"""
        message_lower = user_message.lower()
        
        campaign_keywords = [
            'campaign', 'campaigns', 'active campaign', 'campaign status', 'campaign count',
            'campaign performance', 'campaign success', 'campaign analysis', 'campaign metrics',
            'campaign workflow', 'campaign process', 'campaign steps', 'campaign launch',
            'campaign monitoring', 'campaign optimization', 'campaign best practices', 'campaign tips',
            'how many campaign', 'list campaign', 'show campaign', 'campaign details',
            'campaign recipient', 'campaign target', 'campaign audience', 'campaign segmentation',
            'campaign content', 'campaign template', 'campaign channel', 'campaign communication',
            'campaign report', 'campaign analytics', 'campaign insights', 'campaign data',
            'create campaign', 'new campaign', 'campaign creation', 'campaign setup',
            'campaign schedule', 'campaign timing', 'campaign frequency', 'campaign recurrence',
            'campaign budget', 'campaign cost', 'campaign roi', 'campaign effectiveness',
            'campaign delivery', 'campaign sent', 'campaign delivered', 'campaign opened',
            'campaign clicked', 'campaign response', 'campaign engagement', 'campaign conversion'
        ]
        
        non_campaign_keywords = [
            'weather', 'joke', 'cook', 'recipe', 'homework', 'capital', 'news', 'sports',
            'movie', 'music', 'game', 'travel', 'restaurant', 'shopping', 'fashion',
            'health', 'exercise', 'diet', 'medical', 'doctor', 'school', 'university',
            'politics', 'election', 'government', 'economy', 'stock', 'investment',
            'entertainment', 'celebrity', 'gossip', 'social media', 'facebook', 'instagram',
            'twitter', 'tiktok', 'youtube', 'netflix', 'amazon', 'google', 'apple',
            'microsoft', 'programming', 'coding', 'software', 'hardware', 'gaming',
            'sports', 'football', 'basketball', 'soccer', 'tennis', 'golf', 'baseball',
            'car', 'vehicle', 'automobile', 'house', 'home', 'real estate', 'rent',
            'buy', 'sell', 'price', 'cost', 'money', 'salary', 'job', 'career',
            'relationship', 'dating', 'marriage', 'family', 'children', 'parenting',
            'personal', 'private', 'life', 'lifestyle', 'hobby', 'interest', 'fun'
        ]
        
        upload_keywords = [
            'upload', 'file upload', 'upload performance', 'upload success', 'batch upload',
            'upload failed', 'upload error', 'upload issue', 'why upload failed',
            'upload file', 'upload data', 'upload process', 'upload status',
            'upload completion', 'upload progress', 'upload validation', 'upload format'
        ]
        
        communication_keywords = [
            'email performance', 'whatsapp performance', 'sms performance', 'communication effectiveness', 
            'delivery rate', 'email sent', 'whatsapp sent', 'sms sent', 'message delivery',
            'email opened', 'email clicked', 'whatsapp delivered', 'sms delivered'
        ]
        
        channel_keywords = [
            'channel performance', 'channel analysis', 'channel effectiveness', 'best channel',
            'communication channel', 'email channel', 'whatsapp channel', 'sms channel'
        ]
        
        engagement_keywords = [
            'recipient engagement', 'open rate', 'click rate', 'response rate', 'engagement',
            'customer engagement', 'user engagement', 'interaction rate', 'conversion rate'
        ]
        
        if any(keyword in message_lower for keyword in non_campaign_keywords):
            return 'non_campaign'
        
        elif any(keyword in message_lower for keyword in campaign_keywords):
            if any(keyword in message_lower for keyword in ['campaign performance', 'campaign success', 'campaign analysis', 'campaign metrics']):
                return 'campaign_performance'
            elif any(keyword in message_lower for keyword in ['optimize campaign', 'improve campaign', 'campaign best practices', 'campaign tips']):
                return 'campaign_optimization'
            else:
                return 'campaign_general'
        
        elif any(keyword in message_lower for keyword in upload_keywords):
            return 'upload_analysis'
        
        elif any(keyword in message_lower for keyword in communication_keywords):
            return 'communication_effectiveness'
        
        elif any(keyword in message_lower for keyword in channel_keywords):
            return 'channel_analysis'
        
        elif any(keyword in message_lower for keyword in engagement_keywords):
            return 'recipient_engagement'
        
        else:
            return 'non_campaign'
    
    def _get_specialized_data(self, query_type: str, user_message: str) -> Dict[str, Any]:
        """Fetch specialized data based on query type"""
        try:
            if query_type == 'campaign_performance':
                return self._get_campaign_performance_data()
            elif query_type == 'campaign_general':
                return self._get_campaign_general_data()
            elif query_type == 'upload_analysis':
                return self._get_upload_analysis_data()
            elif query_type == 'communication_effectiveness':
                return self._get_communication_effectiveness_data()
            elif query_type == 'channel_analysis':
                return self._get_channel_analysis_data()
            elif query_type == 'recipient_engagement':
                return self._get_recipient_engagement_data()
            elif query_type == 'upload_troubleshooting':
                return self._get_upload_troubleshooting_data()
            elif query_type == 'campaign_optimization':
                return self._get_campaign_optimization_data()
            elif query_type == 'non_campaign':
                return {'non_campaign': True}
            else:
                return {}
        except Exception as e:
            logger.error(f"Error fetching specialized data for {query_type}: {str(e)}")
            return {}
    
    def _get_campaign_performance_data(self) -> Dict[str, Any]:
        """Get detailed campaign performance data"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            
            campaigns = Campaign.objects.filter(is_deleted=False)
            
            status_performance = campaigns.values('status').annotate(
                count=Count('id'),
                avg_targets=Avg('target_count')
            )
            
            type_performance = campaigns.filter(
                created_at__gte=thirty_days_ago
            ).values('campaign_type__name').annotate(
                count=Count('id'),
                total_targets=Sum('target_count'),
                success_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
            )
            
            recipient_performance = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).aggregate(
                total_recipients=Count('id'),
                email_sent=Count('id', filter=Q(email_status='sent')),
                email_delivered=Count('id', filter=Q(email_status='delivered')),
                email_opened=Count('id', filter=Q(email_engagement='opened')),
                whatsapp_sent=Count('id', filter=Q(whatsapp_status='sent')),
                sms_sent=Count('id', filter=Q(sms_status='sent'))
            )
            
            return {
                'campaign_performance': {
                    'status_performance': list(status_performance),
                    'type_performance': list(type_performance),
                    'recipient_performance': recipient_performance
                }
            }
            
        except Exception as e:
            logger.error(f"Error in campaign performance data: {str(e)}")
            return {'campaign_performance': {}}
    
    def _get_campaign_general_data(self) -> Dict[str, Any]:
        """Get general campaign data for workflow and general questions"""
        try:
            campaigns = Campaign.objects.filter(is_deleted=False)
            
            campaign_stats = {
                'total_campaigns': campaigns.count(),
                'active_campaigns': campaigns.filter(status='active').count(),
                'completed_campaigns': campaigns.filter(status='completed').count(),
                'paused_campaigns': campaigns.filter(status='paused').count(),
            }
            
            recent_campaigns = campaigns.order_by('-created_at')[:5].values(
                'name', 'status', 'campaign_type__name', 'target_count', 'created_at'
            )
            
            campaign_types = campaigns.values('campaign_type__name').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {
                'campaign_general': {
                    'campaign_stats': campaign_stats,
                    'recent_campaigns': list(recent_campaigns),
                    'campaign_types': list(campaign_types)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in campaign general data: {str(e)}")
            return {'campaign_general': {}}
    
    def _get_upload_analysis_data(self) -> Dict[str, Any]:
        """Get detailed upload analysis data"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            
            upload_files = UploadFile.objects.filter(is_deleted=False)
            
            upload_performance = upload_files.values('status').annotate(
                count=Count('id'),
                total_records=Sum('total_records'),
                successful_records=Sum('successful_records'),
                failed_records=Sum('failed_records'),
                avg_success_rate=Avg('successful_records') * 100.0 / Avg('total_records')
            )
            
            recent_trends = upload_files.filter(
                created_at__gte=thirty_days_ago
            ).extra(
                select={'day': 'DATE(created_at)'}
            ).values('day').annotate(
                count=Count('id'),
                total_records=Sum('total_records'),
                successful_records=Sum('successful_records')
            ).order_by('day')
            
            file_type_analysis = upload_files.values('file_type').annotate(
                count=Count('id'),
                avg_success_rate=Avg('successful_records') * 100.0 / Avg('total_records')
            )
            
            return {
                'upload_analysis': {
                    'upload_performance': list(upload_performance),
                    'recent_trends': list(recent_trends),
                    'file_type_analysis': list(file_type_analysis)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in upload analysis data: {str(e)}")
            return {'upload_analysis': {}}
    
    def _get_communication_effectiveness_data(self) -> Dict[str, Any]:
        """Get communication effectiveness data"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            
            email_performance = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('email_status').annotate(
                count=Count('id')
            )
            
            email_engagement = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('email_engagement').annotate(
                count=Count('id')
            )
            
            whatsapp_performance = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('whatsapp_status').annotate(
                count=Count('id')
            )
            
            whatsapp_engagement = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('whatsapp_engagement').annotate(
                count=Count('id')
            )
            
            sms_performance = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('sms_status').annotate(
                count=Count('id')
            )
            
            sms_engagement = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('sms_engagement').annotate(
                count=Count('id')
            )
            
            return {
                'communication_effectiveness': {
                    'email_performance': list(email_performance),
                    'email_engagement': list(email_engagement),
                    'whatsapp_performance': list(whatsapp_performance),
                    'whatsapp_engagement': list(whatsapp_engagement),
                    'sms_performance': list(sms_performance),
                    'sms_engagement': list(sms_engagement)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in communication effectiveness data: {str(e)}")
            return {'communication_effectiveness': {}}
    
    def _get_channel_analysis_data(self) -> Dict[str, Any]:
        """Get channel analysis data"""
        try:
            channel_campaigns = Channel.objects.filter(
                is_deleted=False
            ).annotate(
                campaign_count=Count('campaigns'),
                recipient_count=Count('campaigns__recipients'),
                active_campaigns=Count('campaigns', filter=Q(campaigns__status='active'))
            ).values(
                'name', 'channel_type', 'status', 'campaign_count', 
                'recipient_count', 'active_campaigns'
            )
            
            channel_communication = CommunicationLog.objects.filter(
                communication_date__gte=timezone.now() - timedelta(days=30)
            ).values('channel').annotate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])),
                success_rate=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])) * 100.0 / Count('id')
            )
            
            return {
                'channel_analysis': {
                    'channel_campaigns': list(channel_campaigns),
                    'channel_communication': list(channel_communication)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in channel analysis data: {str(e)}")
            return {'channel_analysis': {}}
    
    def _get_recipient_engagement_data(self) -> Dict[str, Any]:
        """Get recipient engagement data"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            
            engagement_metrics = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).aggregate(
                total_recipients=Count('id'),
                email_opened=Count('id', filter=Q(email_engagement='opened')),
                email_clicked=Count('id', filter=Q(email_engagement='clicked')),
                email_replied=Count('id', filter=Q(email_engagement='replied')),
                whatsapp_read=Count('id', filter=Q(whatsapp_engagement='opened')),
                whatsapp_replied=Count('id', filter=Q(whatsapp_engagement='replied')),
                sms_replied=Count('id', filter=Q(sms_engagement='replied'))
            )
            
            total = engagement_metrics.get('total_recipients', 0)
            if total > 0:
                engagement_metrics['email_open_rate'] = (engagement_metrics.get('email_opened', 0) / total) * 100
                engagement_metrics['email_click_rate'] = (engagement_metrics.get('email_clicked', 0) / total) * 100
                engagement_metrics['email_reply_rate'] = (engagement_metrics.get('email_replied', 0) / total) * 100
                engagement_metrics['whatsapp_read_rate'] = (engagement_metrics.get('whatsapp_read', 0) / total) * 100
                engagement_metrics['whatsapp_reply_rate'] = (engagement_metrics.get('whatsapp_replied', 0) / total) * 100
                engagement_metrics['sms_reply_rate'] = (engagement_metrics.get('sms_replied', 0) / total) * 100
            
            engagement_by_type = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('campaign__campaign_type__name').annotate(
                total_recipients=Count('id'),
                email_opened=Count('id', filter=Q(email_engagement='opened')),
                email_clicked=Count('id', filter=Q(email_engagement='clicked')),
                open_rate=Count('id', filter=Q(email_engagement='opened')) * 100.0 / Count('id'),
                click_rate=Count('id', filter=Q(email_engagement='clicked')) * 100.0 / Count('id')
            )
            
            return {
                'recipient_engagement': {
                    'engagement_metrics': engagement_metrics,
                    'engagement_by_type': list(engagement_by_type)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in recipient engagement data: {str(e)}")
            return {'recipient_engagement': {}}
    
    def _get_upload_troubleshooting_data(self) -> Dict[str, Any]:
        """Get upload troubleshooting data"""
        try:
            failed_uploads = UploadFile.objects.filter(
                is_deleted=False,
                status='failed'
            ).values('file_name', 'file_type', 'error_message', 'created_at').order_by('-created_at')[:10]
            
            error_patterns = UploadFile.objects.filter(
                is_deleted=False,
                status='failed',
                error_message__isnull=False
            ).values('error_message').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            success_by_type = UploadFile.objects.filter(
                is_deleted=False
            ).values('file_type').annotate(
                total=Count('id'),
                successful=Count('id', filter=Q(status='completed')),
                failed=Count('id', filter=Q(status='failed')),
                success_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
            )
            
            return {
                'upload_troubleshooting': {
                    'failed_uploads': list(failed_uploads),
                    'error_patterns': list(error_patterns),
                    'success_by_type': list(success_by_type)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in upload troubleshooting data: {str(e)}")
            return {'upload_troubleshooting': {}}
    
    def _get_campaign_optimization_data(self) -> Dict[str, Any]:
        """Get campaign optimization data"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            
            best_campaigns = Campaign.objects.filter(
                is_deleted=False,
                created_at__gte=thirty_days_ago
            ).annotate(
                recipient_count=Count('recipients'),
                delivered_count=Count('recipients', filter=Q(recipients__email_status='delivered')),
                opened_count=Count('recipients', filter=Q(recipients__email_engagement='opened')),
                clicked_count=Count('recipients', filter=Q(recipients__email_engagement='clicked'))
            ).filter(
                recipient_count__gt=0
            ).extra(
                select={
                    'delivery_rate': 'delivered_count * 100.0 / recipient_count',
                    'open_rate': 'opened_count * 100.0 / delivered_count',
                    'click_rate': 'clicked_count * 100.0 / opened_count'
                }
            ).order_by('-delivery_rate')[:5]
            
            send_time_analysis = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago,
                email_sent_at__isnull=False
            ).extra(
                select={'hour': 'EXTRACT(hour FROM email_sent_at)'}
            ).values('hour').annotate(
                count=Count('id'),
                opened_count=Count('id', filter=Q(email_engagement='opened')),
                open_rate=Count('id', filter=Q(email_engagement='opened')) * 100.0 / Count('id')
            ).order_by('-open_rate')
            
            subject_performance = Campaign.objects.filter(
                is_deleted=False,
                created_at__gte=thirty_days_ago,
                subject_line__isnull=False
            ).annotate(
                recipient_count=Count('recipients'),
                opened_count=Count('recipients', filter=Q(recipients__email_engagement='opened')),
                clicked_count=Count('recipients', filter=Q(recipients__email_engagement='clicked'))
            ).filter(
                recipient_count__gt=0
            ).extra(
                select={
                    'open_rate': 'opened_count * 100.0 / recipient_count',
                    'click_rate': 'clicked_count * 100.0 / opened_count'
                }
            ).values('subject_line', 'open_rate', 'click_rate', 'recipient_count').order_by('-open_rate')[:10]
            
            return {
                'campaign_optimization': {
                    'best_campaigns': list(best_campaigns),
                    'send_time_analysis': list(send_time_analysis),
                    'subject_performance': list(subject_performance)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in campaign optimization data: {str(e)}")
            return {'campaign_optimization': {}}
    
    def _create_system_prompt(self, dashboard_data: Dict[str, Any], user=None, query_type: str = 'general') -> str:
        """Create system prompt for upload and campaign chatbot"""
        
        specialized_context = self._build_specialized_context(dashboard_data, query_type)
        
        if query_type == 'non_campaign':
            return f"""
You are an AI assistant for Renew-IQ's Upload and Campaign Management system. 
You ONLY help users with questions related to campaigns, uploads, and communication management.

{specialized_context}

CRITICAL INSTRUCTIONS:
You MUST respond with EXACTLY this message and nothing else:
"Sorry, I can only help with campaign-related questions. Please ask me about campaigns, uploads, or communication management."

DO NOT:
- Provide any other information
- Give explanations
- Offer alternatives
- Be creative or helpful in other ways
- Interpret the question differently

ONLY respond with the exact message above.
"""
        
        return f"""
You are an AI assistant for Renew-IQ's Upload and Campaign Management system. 
You help users analyze their campaign performance, upload success rates, communication effectiveness, and provide optimization insights.

CURRENT SYSTEM DATA:
- Total Campaigns: {dashboard_data.get('campaign_stats', {}).get('total_campaigns', 0)}
- Active Campaigns: {dashboard_data.get('campaign_stats', {}).get('active_campaigns', 0)}
- Completed Campaigns: {dashboard_data.get('campaign_stats', {}).get('completed_campaigns', 0)}
- Failed Campaigns: {dashboard_data.get('campaign_stats', {}).get('failed_campaigns', 0)}

- Total Uploads: {dashboard_data.get('upload_stats', {}).get('total_uploads', 0)}
- Successful Uploads: {dashboard_data.get('upload_stats', {}).get('successful_uploads', 0)}
- Failed Uploads: {dashboard_data.get('upload_stats', {}).get('failed_uploads', 0)}
- Processing Uploads: {dashboard_data.get('upload_stats', {}).get('processing_uploads', 0)}

- Total Recipients: {dashboard_data.get('recipient_stats', {}).get('total_recipients', 0)}
- Email Sent: {dashboard_data.get('recipient_stats', {}).get('email_sent', 0)}
- Email Delivered: {dashboard_data.get('recipient_stats', {}).get('email_delivered', 0)}
- Email Opened: {dashboard_data.get('recipient_stats', {}).get('email_opened', 0)}
- Email Clicked: {dashboard_data.get('recipient_stats', {}).get('email_clicked', 0)}
- WhatsApp Sent: {dashboard_data.get('recipient_stats', {}).get('whatsapp_sent', 0)}
- SMS Sent: {dashboard_data.get('recipient_stats', {}).get('sms_sent', 0)}

{specialized_context}

CRITICAL INSTRUCTIONS:
1. ALWAYS provide specific, data-driven insights based on the actual data provided above
2. Use exact numbers, percentages, and metrics from the database
3. Identify specific patterns, trends, and anomalies in the data
4. Provide actionable recommendations based on the actual data analysis
5. When discussing campaign performance, use the specific metrics provided
6. For upload analysis, focus on success rates, error patterns, and file type performance
7. For communication effectiveness, analyze delivery rates, open rates, click rates, and engagement
8. For channel analysis, compare performance across different channels
9. Always explain the "why" behind the data - what factors contribute to the current situation
10. Provide specific, measurable action items that can improve the metrics
11. Use the specialized data sections to provide deep, contextual analysis
12. Never give generic advice - always tie recommendations to the specific data patterns observed

RESPONSE FORMAT:
- Start with key findings from the data
- Explain the significance of these findings
- Provide specific recommendations with expected impact
- Include actionable next steps
- Use data to support all claims and recommendations
"""
    
    def _build_specialized_context(self, dashboard_data: Dict[str, Any], query_type: str) -> str:
        """Build specialized context based on query type"""
        if query_type == 'campaign_performance':
            return self._build_campaign_performance_context(dashboard_data.get('campaign_performance', {}))
        elif query_type == 'campaign_general':
            return self._build_campaign_general_context(dashboard_data.get('campaign_general', {}))
        elif query_type == 'upload_analysis':
            return self._build_upload_analysis_context(dashboard_data.get('upload_analysis', {}))
        elif query_type == 'communication_effectiveness':
            return self._build_communication_effectiveness_context(dashboard_data.get('communication_effectiveness', {}))
        elif query_type == 'channel_analysis':
            return self._build_channel_analysis_context(dashboard_data.get('channel_analysis', {}))
        elif query_type == 'recipient_engagement':
            return self._build_recipient_engagement_context(dashboard_data.get('recipient_engagement', {}))
        elif query_type == 'upload_troubleshooting':
            return self._build_upload_troubleshooting_context(dashboard_data.get('upload_troubleshooting', {}))
        elif query_type == 'campaign_optimization':
            return self._build_campaign_optimization_context(dashboard_data.get('campaign_optimization', {}))
        elif query_type == 'non_campaign':
            return self._build_non_campaign_context()
        else:
            return ""
    
    def _build_campaign_performance_context(self, campaign_data: Dict[str, Any]) -> str:
        """Build context for campaign performance analysis"""
        if not campaign_data:
            return ""
        
        context = "\n\nCAMPAIGN PERFORMANCE ANALYSIS:\n"
        
        status_performance = campaign_data.get('status_performance', [])
        if status_performance:
            context += "\nCAMPAIGN STATUS PERFORMANCE:\n"
            for status in status_performance:
                context += f"- {status.get('status', 'Unknown')}: {status.get('count', 0)} campaigns (Avg Targets: {status.get('avg_targets', 0):.1f})\n"
        
        type_performance = campaign_data.get('type_performance', [])
        if type_performance:
            context += "\nCAMPAIGN TYPE PERFORMANCE (30 days):\n"
            for campaign_type in type_performance:
                context += f"- {campaign_type.get('campaign_type__name', 'Unknown')}: {campaign_type.get('count', 0)} campaigns, {campaign_type.get('success_rate', 0):.1f}% success rate\n"
                context += f"  Total Targets: {campaign_type.get('total_targets', 0)}\n"
        
        recipient_performance = campaign_data.get('recipient_performance', {})
        if recipient_performance:
            context += "\nRECIPIENT PERFORMANCE (30 days):\n"
            context += f"- Total Recipients: {recipient_performance.get('total_recipients', 0)}\n"
            context += f"- Email Sent: {recipient_performance.get('email_sent', 0)}\n"
            context += f"- Email Delivered: {recipient_performance.get('email_delivered', 0)}\n"
            context += f"- Email Opened: {recipient_performance.get('email_opened', 0)}\n"
            context += f"- WhatsApp Sent: {recipient_performance.get('whatsapp_sent', 0)}\n"
            context += f"- SMS Sent: {recipient_performance.get('sms_sent', 0)}\n"
        
        return context
    
    def _build_upload_analysis_context(self, upload_data: Dict[str, Any]) -> str:
        """Build context for upload analysis"""
        if not upload_data:
            return ""
        
        context = "\n\nUPLOAD ANALYSIS:\n"
        
        upload_performance = upload_data.get('upload_performance', [])
        if upload_performance:
            context += "\nUPLOAD PERFORMANCE BY STATUS:\n"
            for upload in upload_performance:
                context += f"- {upload.get('status', 'Unknown')}: {upload.get('count', 0)} uploads\n"
                context += f"  Total Records: {upload.get('total_records', 0)}, Successful: {upload.get('successful_records', 0)}, Failed: {upload.get('failed_records', 0)}\n"
                if upload.get('avg_success_rate'):
                    context += f"  Avg Success Rate: {upload.get('avg_success_rate', 0):.1f}%\n"
        
        recent_trends = upload_data.get('recent_trends', [])
        if recent_trends:
            context += "\nRECENT UPLOAD TRENDS (30 days):\n"
            for trend in recent_trends:
                context += f"- {trend.get('day')}: {trend.get('count', 0)} uploads, {trend.get('total_records', 0)} records, {trend.get('successful_records', 0)} successful\n"
        
        file_type_analysis = upload_data.get('file_type_analysis', [])
        if file_type_analysis:
            context += "\nFILE TYPE ANALYSIS:\n"
            for file_type in file_type_analysis:
                context += f"- {file_type.get('file_type', 'Unknown')}: {file_type.get('count', 0)} uploads, {file_type.get('avg_success_rate', 0):.1f}% avg success rate\n"
        
        return context
    
    def _build_communication_effectiveness_context(self, comm_data: Dict[str, Any]) -> str:
        """Build context for communication effectiveness"""
        if not comm_data:
            return ""
        
        context = "\n\nCOMMUNICATION EFFECTIVENESS ANALYSIS:\n"
        
        email_performance = comm_data.get('email_performance', [])
        if email_performance:
            context += "\nEMAIL PERFORMANCE (30 days):\n"
            for email in email_performance:
                context += f"- {email.get('email_status', 'Unknown')}: {email.get('count', 0)} emails\n"
        
        email_engagement = comm_data.get('email_engagement', [])
        if email_engagement:
            context += "\nEMAIL ENGAGEMENT (30 days):\n"
            for engagement in email_engagement:
                context += f"- {engagement.get('email_engagement', 'Unknown')}: {engagement.get('count', 0)} recipients\n"
        
        whatsapp_performance = comm_data.get('whatsapp_performance', [])
        if whatsapp_performance:
            context += "\nWHATSAPP PERFORMANCE (30 days):\n"
            for whatsapp in whatsapp_performance:
                context += f"- {whatsapp.get('whatsapp_status', 'Unknown')}: {whatsapp.get('count', 0)} messages\n"
        
        sms_performance = comm_data.get('sms_performance', [])
        if sms_performance:
            context += "\nSMS PERFORMANCE (30 days):\n"
            for sms in sms_performance:
                context += f"- {sms.get('sms_status', 'Unknown')}: {sms.get('count', 0)} messages\n"
        
        return context
    
    def _build_channel_analysis_context(self, channel_data: Dict[str, Any]) -> str:
        """Build context for channel analysis"""
        if not channel_data:
            return ""
        
        context = "\n\nCHANNEL ANALYSIS:\n"
        
        channel_campaigns = channel_data.get('channel_campaigns', [])
        if channel_campaigns:
            context += "\nCHANNEL CAMPAIGN PERFORMANCE:\n"
            for channel in channel_campaigns:
                context += f"- {channel.get('name', 'Unknown')} ({channel.get('channel_type', 'Unknown')}): {channel.get('campaign_count', 0)} campaigns, {channel.get('recipient_count', 0)} recipients\n"
                context += f"  Status: {channel.get('status', 'Unknown')}, Active: {channel.get('active_campaigns', 0)}\n"
        
        channel_communication = channel_data.get('channel_communication', [])
        if channel_communication:
            context += "\nCHANNEL COMMUNICATION PERFORMANCE (30 days):\n"
            for comm in channel_communication:
                context += f"- {comm.get('channel', 'Unknown')}: {comm.get('total_attempts', 0)} attempts, {comm.get('success_rate', 0):.1f}% success rate\n"
        
        return context
    
    def _build_recipient_engagement_context(self, engagement_data: Dict[str, Any]) -> str:
        """Build context for recipient engagement"""
        if not engagement_data:
            return ""
        
        context = "\n\nRECIPIENT ENGAGEMENT ANALYSIS:\n"
        
        engagement_metrics = engagement_data.get('engagement_metrics', {})
        if engagement_metrics:
            context += "\nOVERALL ENGAGEMENT METRICS (30 days):\n"
            context += f"- Total Recipients: {engagement_metrics.get('total_recipients', 0)}\n"
            context += f"- Email Open Rate: {engagement_metrics.get('email_open_rate', 0):.1f}%\n"
            context += f"- Email Click Rate: {engagement_metrics.get('email_click_rate', 0):.1f}%\n"
            context += f"- Email Reply Rate: {engagement_metrics.get('email_reply_rate', 0):.1f}%\n"
            context += f"- WhatsApp Read Rate: {engagement_metrics.get('whatsapp_read_rate', 0):.1f}%\n"
            context += f"- WhatsApp Reply Rate: {engagement_metrics.get('whatsapp_reply_rate', 0):.1f}%\n"
            context += f"- SMS Reply Rate: {engagement_metrics.get('sms_reply_rate', 0):.1f}%\n"
        
        engagement_by_type = engagement_data.get('engagement_by_type', [])
        if engagement_by_type:
            context += "\nENGAGEMENT BY CAMPAIGN TYPE:\n"
            for campaign_type in engagement_by_type:
                context += f"- {campaign_type.get('campaign__campaign_type__name', 'Unknown')}: {campaign_type.get('total_recipients', 0)} recipients\n"
                context += f"  Open Rate: {campaign_type.get('open_rate', 0):.1f}%, Click Rate: {campaign_type.get('click_rate', 0):.1f}%\n"
        
        return context
    
    def _build_upload_troubleshooting_context(self, troubleshooting_data: Dict[str, Any]) -> str:
        """Build context for upload troubleshooting"""
        if not troubleshooting_data:
            return ""
        
        context = "\n\nUPLOAD TROUBLESHOOTING ANALYSIS:\n"
        
        failed_uploads = troubleshooting_data.get('failed_uploads', [])
        if failed_uploads:
            context += "\nRECENT FAILED UPLOADS:\n"
            for upload in failed_uploads:
                context += f"- {upload.get('file_name', 'Unknown')} ({upload.get('file_type', 'Unknown')}): {upload.get('error_message', 'No error message')}\n"
                context += f"  Date: {upload.get('created_at', 'Unknown')}\n"
        
        error_patterns = troubleshooting_data.get('error_patterns', [])
        if error_patterns:
            context += "\nCOMMON ERROR PATTERNS:\n"
            for error in error_patterns:
                context += f"- {error.get('error_message', 'Unknown')}: {error.get('count', 0)} occurrences\n"
        
        success_by_type = troubleshooting_data.get('success_by_type', [])
        if success_by_type:
            context += "\nSUCCESS RATE BY FILE TYPE:\n"
            for file_type in success_by_type:
                context += f"- {file_type.get('file_type', 'Unknown')}: {file_type.get('success_rate', 0):.1f}% success rate\n"
                context += f"  Total: {file_type.get('total', 0)}, Successful: {file_type.get('successful', 0)}, Failed: {file_type.get('failed', 0)}\n"
        
        return context
    
    def _build_campaign_optimization_context(self, optimization_data: Dict[str, Any]) -> str:
        """Build context for campaign optimization"""
        if not optimization_data:
            return ""
        
        context = "\n\nCAMPAIGN OPTIMIZATION INSIGHTS:\n"
        
        best_campaigns = optimization_data.get('best_campaigns', [])
        if best_campaigns:
            context += "\nTOP PERFORMING CAMPAIGNS (30 days):\n"
            for campaign in best_campaigns:
                context += f"- {campaign.name}: {campaign.recipient_count} recipients\n"
                context += f"  Delivery Rate: {getattr(campaign, 'delivery_rate', 0):.1f}%, Open Rate: {getattr(campaign, 'open_rate', 0):.1f}%, Click Rate: {getattr(campaign, 'click_rate', 0):.1f}%\n"
        
        send_time_analysis = optimization_data.get('send_time_analysis', [])
        if send_time_analysis:
            context += "\nOPTIMAL SEND TIMES:\n"
            for time_data in send_time_analysis:
                context += f"- Hour {time_data.get('hour', 'Unknown')}: {time_data.get('open_rate', 0):.1f}% open rate ({time_data.get('count', 0)} emails)\n"
        
        subject_performance = optimization_data.get('subject_performance', [])
        if subject_performance:
            context += "\nTOP PERFORMING SUBJECT LINES:\n"
            for subject in subject_performance:
                context += f"- '{subject.get('subject_line', 'Unknown')}': {subject.get('open_rate', 0):.1f}% open rate, {subject.get('click_rate', 0):.1f}% click rate\n"
                context += f"  Recipients: {subject.get('recipient_count', 0)}\n"
        
        return context
    
    def _build_campaign_general_context(self, campaign_data: Dict[str, Any]) -> str:
        """Build context for general campaign questions"""
        if not campaign_data:
            return ""
        
        context = "\n\nCAMPAIGN INFORMATION:\n"
        
        campaign_stats = campaign_data.get('campaign_stats', {})
        if campaign_stats:
            context += "\nCURRENT CAMPAIGN STATISTICS:\n"
            context += f"- Total Campaigns: {campaign_stats.get('total_campaigns', 0)}\n"
            context += f"- Active Campaigns: {campaign_stats.get('active_campaigns', 0)}\n"
            context += f"- Completed Campaigns: {campaign_stats.get('completed_campaigns', 0)}\n"
            context += f"- Paused Campaigns: {campaign_stats.get('paused_campaigns', 0)}\n"
        
        recent_campaigns = campaign_data.get('recent_campaigns', [])
        if recent_campaigns:
            context += "\nRECENT CAMPAIGNS:\n"
            for campaign in recent_campaigns:
                context += f"- {campaign.get('name', 'Unknown')} ({campaign.get('status', 'Unknown')})\n"
                context += f"  Type: {campaign.get('campaign_type__name', 'Unknown')}, Targets: {campaign.get('target_count', 0)}\n"
        
        campaign_types = campaign_data.get('campaign_types', [])
        if campaign_types:
            context += "\nCAMPAIGN TYPES AVAILABLE:\n"
            for campaign_type in campaign_types:
                context += f"- {campaign_type.get('campaign_type__name', 'Unknown')}: {campaign_type.get('count', 0)} campaigns\n"
        
        return context
    
    def _build_non_campaign_context(self) -> str:
        """Build context for non-campaign questions"""
        return "\n\nIMPORTANT: This question is not related to campaigns or uploads. Please respond with the standard non-campaign message."
    
    def get_quick_suggestions(self) -> List[Dict[str, str]]:
        """Get quick suggestions for upload and campaign queries"""
        return [
            {
                "id": "analyze_campaign_performance",
                "title": "Analyze my current campaign performance",
                "description": "Get insights on campaign success rates, delivery metrics, and engagement trends"
            },
            {
                "id": "upload_analysis",
                "title": "What's my upload success rate?",
                "description": "Analyze file upload performance, error patterns, and success rates by file type"
            },
            {
                "id": "communication_effectiveness",
                "title": "How effective are my communication channels?",
                "description": "Compare email, WhatsApp, and SMS performance metrics"
            },
            {
                "id": "recipient_engagement",
                "title": "What's my recipient engagement rate?",
                "description": "Analyze open rates, click rates, and response rates across campaigns"
            },
            {
                "id": "upload_troubleshooting",
                "title": "Why are my uploads failing?",
                "description": "Identify common upload errors and provide troubleshooting solutions"
            },
            {
                "id": "campaign_optimization",
                "title": "How can I optimize my campaigns?",
                "description": "Get recommendations for improving campaign performance and engagement"
            },
            {
                "id": "channel_analysis",
                "title": "Which channels work best for my campaigns?",
                "description": "Analyze channel performance and identify the most effective communication methods"
            }
        ]


# Global upload chatbot service instance - lazy initialization
_upload_chatbot_service_instance = None

def get_upload_chatbot_service():
    """Get or create the upload chatbot service instance"""
    global _upload_chatbot_service_instance
    if _upload_chatbot_service_instance is None:
        _upload_chatbot_service_instance = UploadChatbotService()
    return _upload_chatbot_service_instance

# For backward compatibility - lazy initialization
class LazyUploadChatbotService:
    def __init__(self):
        self._service = None
    
    def __getattr__(self, name):
        if self._service is None:
            self._service = get_upload_chatbot_service()
        return getattr(self._service, name)

upload_chatbot_service = LazyUploadChatbotService()
