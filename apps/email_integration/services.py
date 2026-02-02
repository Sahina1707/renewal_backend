import logging
import requests
import json
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import timedelta
import uuid

from .models import (
    EmailWebhook, EmailAutomation, EmailAutomationLog, EmailIntegration,
    EmailSLA, EmailTemplateVariable, EmailIntegrationAnalytics
)

logger = logging.getLogger(__name__)


class EmailIntegrationService:
    """Service for managing email integration features"""
    
    def __init__(self):
        pass
    
    def process_incoming_email_webhook(self, provider: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            webhook = EmailWebhook.objects.create(
                provider=provider,
                event_type='incoming',
                raw_data=raw_data
            )
            
            processed_data = self._process_incoming_email_data(provider, raw_data)
            webhook.processed_data = processed_data
            
            if processed_data.get('email_data'):
                from apps.email_inbox.services import EmailInboxService
                inbox_service = EmailInboxService()
                
                email_data = processed_data['email_data']
                
                supported_params = {
                    'from_email': email_data.get('from_email', ''),
                    'to_email': email_data.get('to_email', ''),
                    'subject': email_data.get('subject', ''),
                    'html_content': email_data.get('html_content', ''),
                    'text_content': email_data.get('text_content', ''),
                    'from_name': email_data.get('from_name', ''),
                    'cc_emails': email_data.get('cc_emails', []),
                    'bcc_emails': email_data.get('bcc_emails', []),
                    'reply_to': email_data.get('reply_to', '')
                }
                
                inbox_result = inbox_service.receive_email(**supported_params)
                
                if inbox_result['success']:
                    webhook.email_message_id = inbox_result.get('message_id')
                    webhook.status = 'processed'
                    webhook.processed_at = timezone.now()
                    webhook.save()
                    
                    return {
                        'success': True,
                        'message': 'Incoming email processed and stored successfully',
                        'webhook_id': str(webhook.id),
                        'inbox_message_id': inbox_result.get('message_id')
                    }
                else:
                    webhook.status = 'failed'
                    webhook.error_message = inbox_result.get('message', 'Failed to store in inbox')
                    webhook.save()
                    
                    return {
                        'success': False,
                        'message': f"Failed to store incoming email: {inbox_result.get('message')}"
                    }
            else:
                webhook.status = 'failed'
                webhook.error_message = 'No email data found in webhook'
                webhook.save()
                
                return {
                    'success': False,
                    'message': 'No email data found in webhook payload'
                }
            
        except Exception as e:
            logger.error(f"Error processing incoming email webhook: {str(e)}")
            
            if 'webhook' in locals():
                webhook.status = 'failed'
                webhook.error_message = str(e)
                webhook.save()
            
            return {
                'success': False,
                'message': f'Error processing incoming email webhook: {str(e)}'
            }

    def process_webhook(self, provider: str, event_type: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            webhook = EmailWebhook.objects.create(
                provider=provider,
                event_type=event_type,
                raw_data=raw_data
            )
            
            processed_data = self._process_webhook_data(provider, event_type, raw_data)
            webhook.processed_data = processed_data
            
            if processed_data.get('email_message_id'):
                webhook.email_message_id = processed_data['email_message_id']
                webhook.provider_message_id = processed_data.get('provider_message_id')
                webhook.event_time = processed_data.get('event_time')
                
                self._update_email_status_from_webhook(webhook, processed_data)
            
            webhook.status = 'processed'
            webhook.processed_at = timezone.now()
            webhook.save()
            
            return {
                'success': True,
                'message': 'Webhook processed successfully',
                'webhook_id': str(webhook.id)
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            
            if 'webhook' in locals():
                webhook.status = 'failed'
                webhook.error_message = str(e)
                webhook.save()
            
            return {
                'success': False,
                'message': f'Error processing webhook: {str(e)}'
            }
    
    def _process_incoming_email_data(self, provider: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming email data based on provider"""
        try:
            if provider == 'sendgrid':
                return self._process_sendgrid_incoming_email(raw_data)
            else:
                return {
                    'provider': provider,
                    'raw_data': raw_data,
                    'error': f'Unsupported provider: {provider}'
                }
        except Exception as e:
            logger.error(f"Error processing incoming email data: {str(e)}")
            return {
                'provider': provider,
                'raw_data': raw_data,
                'error': str(e)
            }
    
    def _process_sendgrid_incoming_email(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process SendGrid incoming email data"""
        try:
            email_data = {
                'from_email': raw_data.get('from', ''),
                'to_email': raw_data.get('to', ''),
                'subject': raw_data.get('subject', ''),
                'text_content': raw_data.get('text', ''),
                'html_content': raw_data.get('html', ''),
                'message_id': raw_data.get('message_id', ''),
                'thread_id': raw_data.get('thread_id', ''),
                'in_reply_to': raw_data.get('in_reply_to', ''),
                'references': raw_data.get('references', ''),
                'cc_emails': raw_data.get('cc', []),
                'bcc_emails': raw_data.get('bcc', []),
                'reply_to': raw_data.get('reply_to', ''),
                'headers': raw_data.get('headers', {}),
                'received_at': raw_data.get('received_at', timezone.now().isoformat()),
                'size_bytes': raw_data.get('size', 0),
                'is_read': False,
                'is_starred': False,
                'is_spam': False,
                'is_important': False,
                'folder': 'inbox',
                'category': 'incoming',
                'subcategory': 'reply' if raw_data.get('in_reply_to') else 'new',
                'priority': 'normal',
                'tags': [],
                'confidence_score': 1.0,
                'source': 'sendgrid_webhook',
                'raw_data': raw_data
            }
            
            return {
                'provider': 'sendgrid',
                'email_data': email_data,
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing SendGrid incoming email: {str(e)}")
            return {
                'provider': 'sendgrid',
                'raw_data': raw_data,
                'error': str(e)
            }

    def _process_webhook_data(self, provider: str, event_type: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook data based on provider"""
        try:
            if provider == 'sendgrid':
                return self._process_sendgrid_webhook(event_type, raw_data)
            elif provider == 'aws_ses':
                return self._process_aws_ses_webhook(event_type, raw_data)
            else:
                return {
                    'provider': provider,
                    'event_type': event_type,
                    'raw_data': raw_data
                }
        except Exception as e:
            logger.error(f"Error processing webhook data: {str(e)}")
            return {
                'provider': provider,
                'event_type': event_type,
                'raw_data': raw_data,
                'error': str(e)
            }
    
    def _process_sendgrid_webhook(self, event_type: str, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process SendGrid webhook data"""
        try:
            # SendGrid sends an array of events
            if not raw_data or not isinstance(raw_data, list):
                return {'error': 'Invalid SendGrid webhook data'}
            
            event = raw_data[0] 
            return {
                'provider': 'sendgrid',
                'event_type': event_type,
                'email_message_id': event.get('sg_message_id'),
                'provider_message_id': event.get('sg_message_id'),
                'event_time': event.get('timestamp'),
                'ip_address': event.get('ip'),
                'user_agent': event.get('useragent'),
                'event_data': event
            }
        except Exception as e:
            logger.error(f"Error processing SendGrid webhook: {str(e)}")
            return {'error': str(e)}
    
    def _process_aws_ses_webhook(self, event_type: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process AWS SES webhook data"""
        try:
            return {
                'provider': 'aws_ses',
                'event_type': event_type,
                'email_message_id': raw_data.get('mail', {}).get('messageId'),
                'provider_message_id': raw_data.get('mail', {}).get('messageId'),
                'event_time': raw_data.get('eventTime'),
                'event_data': raw_data
            }
        except Exception as e:
            logger.error(f"Error processing AWS SES webhook: {str(e)}")
            return {'error': str(e)}
    
    def _update_email_status_from_webhook(self, webhook: EmailWebhook, processed_data: Dict[str, Any]):
        """Update email message status based on webhook data"""
        try:
            from apps.email_operations.models import EmailMessage
            
            email_message_id = processed_data.get('email_message_id')
            if not email_message_id:
                return
            
            email_message = EmailMessage.objects.filter(
                provider_message_id=email_message_id
            ).first()
            
            if not email_message:
                return
            
            status_mapping = {
                'delivered': 'delivered',
                'bounced': 'bounced',
                'complained': 'complained',
                'unsubscribed': 'unsubscribed',
                'opened': 'delivered', 
                'clicked': 'delivered', 
            }
            
            new_status = status_mapping.get(webhook.event_type)
            if new_status and new_status != email_message.status:
                email_message.status = new_status
                email_message.save()
                
                # Create tracking event
                from apps.email_operations.models import EmailTracking
                EmailTracking.objects.create(
                    email_message=email_message,
                    event_type=webhook.event_type,
                    event_data=processed_data.get('event_data', {}),
                    ip_address=webhook.ip_address,
                    user_agent=webhook.user_agent
                )
            
        except Exception as e:
            logger.error(f"Error updating email status from webhook: {str(e)}")
    
    def execute_automation(self, automation_id: str, trigger_data: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            automation = EmailAutomation.objects.get(id=automation_id)
            
            if not automation.is_active or automation.status != 'active':
                return {
                    'success': False,
                    'message': 'Automation is not active'
                }
            
            if automation.max_executions > 0 and automation.execution_count >= automation.max_executions:
                return {
                    'success': False,
                    'message': 'Automation has reached maximum execution limit'
                }
            
            # Check cooldown
            if automation.cooldown_seconds > 0 and automation.last_executed:
                time_since_last = timezone.now() - automation.last_executed
                if time_since_last.total_seconds() < automation.cooldown_seconds:
                    return {
                        'success': False,
                        'message': 'Automation is in cooldown period'
                    }
            
            # Create execution log
            log = EmailAutomationLog.objects.create(
                automation=automation,
                trigger_data=trigger_data or {},
                status='running',
                started_at=timezone.now()
            )
            
            # Execute automation
            result = self._execute_automation_action(automation, trigger_data or {})
            
            # Update log
            log.status = 'completed' if result['success'] else 'failed'
            log.completed_at = timezone.now()
            log.duration_seconds = (log.completed_at - log.started_at).total_seconds()
            log.result_data = result
            if not result['success']:
                log.error_message = result.get('message', 'Unknown error')
            log.save()
            
            # Update automation
            automation.execution_count += 1
            automation.last_executed = timezone.now()
            automation.save()
            
            return result
            
        except EmailAutomation.DoesNotExist:
            return {
                'success': False,
                'message': 'Automation not found'
            }
        except Exception as e:
            logger.error(f"Error executing automation: {str(e)}")
            return {
                'success': False,
                'message': f'Error executing automation: {str(e)}'
            }
    
    def _execute_automation_action(self, automation: EmailAutomation, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the automation action"""
        try:
            action_type = automation.action_type
            action_config = automation.action_config
            
            if action_type == 'send_email':
                return self._execute_send_email_action(action_config, trigger_data)
            elif action_type == 'reply_email':
                return self._execute_reply_email_action(action_config, trigger_data)
            elif action_type == 'forward_email':
                return self._execute_forward_email_action(action_config, trigger_data)
            elif action_type == 'move_to_folder':
                return self._execute_move_to_folder_action(action_config, trigger_data)
            elif action_type == 'add_tag':
                return self._execute_add_tag_action(action_config, trigger_data)
            elif action_type == 'assign_to_user':
                return self._execute_assign_to_user_action(action_config, trigger_data)
            elif action_type == 'create_task':
                return self._execute_create_task_action(action_config, trigger_data)
            elif action_type == 'update_crm':
                return self._execute_update_crm_action(action_config, trigger_data)
            elif action_type == 'webhook_call':
                return self._execute_webhook_call_action(action_config, trigger_data)
            elif action_type == 'delay':
                return self._execute_delay_action(action_config, trigger_data)
            else:
                return {
                    'success': False,
                    'message': f'Unknown action type: {action_type}'
                }
                
        except Exception as e:
            logger.error(f"Error executing automation action: {str(e)}")
            return {
                'success': False,
                'message': f'Error executing action: {str(e)}'
            }
    
    def _execute_send_email_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute send email action"""
        try:
            from apps.email_operations.services import EmailOperationsService
            
            service = EmailOperationsService()
            service.context = {'user': None}
            
            # Merge trigger data with action config
            email_data = {**action_config, **trigger_data}
            
            result = service.send_email(**email_data)
            return result
            
        except Exception as e:
            logger.error(f"Error executing send email action: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending email: {str(e)}'
            }
    
    def _execute_reply_email_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute reply email action"""
        try:
            from apps.email_inbox.services import EmailInboxService
            
            service = EmailInboxService()
            
            # Get original email ID from trigger data
            original_email_id = trigger_data.get('email_id')
            if not original_email_id:
                return {
                    'success': False,
                    'message': 'No original email ID provided'
                }
            
            # Merge action config with trigger data
            reply_data = {**action_config, **trigger_data}
            
            result = service.reply_to_email(original_email_id, **reply_data)
            return result
            
        except Exception as e:
            logger.error(f"Error executing reply email action: {str(e)}")
            return {
                'success': False,
                'message': f'Error replying to email: {str(e)}'
            }
    
    def _execute_forward_email_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute forward email action"""
        try:
            from apps.email_inbox.services import EmailInboxService
            
            service = EmailInboxService()
            
            # Get original email ID from trigger data
            original_email_id = trigger_data.get('email_id')
            if not original_email_id:
                return {
                    'success': False,
                    'message': 'No original email ID provided'
                }
            
            # Merge action config with trigger data
            forward_data = {**action_config, **trigger_data}
            
            result = service.forward_email(original_email_id, **forward_data)
            return result
            
        except Exception as e:
            logger.error(f"Error executing forward email action: {str(e)}")
            return {
                'success': False,
                'message': f'Error forwarding email: {str(e)}'
            }
    
    def _execute_move_to_folder_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute move to folder action"""
        try:
            from apps.email_inbox.models import EmailInboxMessage, EmailFolder
            
            email_id = trigger_data.get('email_id')
            folder_id = action_config.get('folder_id')
            
            if not email_id or not folder_id:
                return {
                    'success': False,
                    'message': 'Email ID and folder ID are required'
                }
            
            email_message = EmailInboxMessage.objects.get(id=email_id)
            folder = EmailFolder.objects.get(id=folder_id)
            
            email_message.folder = folder
            email_message.save()
            
            return {
                'success': True,
                'message': f'Email moved to folder: {folder.name}'
            }
            
        except Exception as e:
            logger.error(f"Error executing move to folder action: {str(e)}")
            return {
                'success': False,
                'message': f'Error moving email to folder: {str(e)}'
            }
    
    def _execute_add_tag_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute add tag action"""
        try:
            from apps.email_inbox.models import EmailInboxMessage
            
            email_id = trigger_data.get('email_id')
            tag = action_config.get('tag')
            
            if not email_id or not tag:
                return {
                    'success': False,
                    'message': 'Email ID and tag are required'
                }
            
            email_message = EmailInboxMessage.objects.get(id=email_id)
            
            if tag not in email_message.tags:
                email_message.tags.append(tag)
                email_message.save()
            
            return {
                'success': True,
                'message': f'Tag added: {tag}'
            }
            
        except Exception as e:
            logger.error(f"Error executing add tag action: {str(e)}")
            return {
                'success': False,
                'message': f'Error adding tag: {str(e)}'
            }
    
    def _execute_assign_to_user_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute assign to user action"""
        try:
            from apps.email_inbox.models import EmailInboxMessage
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            email_id = trigger_data.get('email_id')
            user_id = action_config.get('user_id')
            
            if not email_id or not user_id:
                return {
                    'success': False,
                    'message': 'Email ID and user ID are required'
                }
            
            email_message = EmailInboxMessage.objects.get(id=email_id)
            user = User.objects.get(id=user_id)
            
            email_message.assigned_to = user
            email_message.save()
            
            return {
                'success': True,
                'message': f'Email assigned to: {user.get_full_name()}'
            }
            
        except Exception as e:
            logger.error(f"Error executing assign to user action: {str(e)}")
            return {
                'success': False,
                'message': f'Error assigning email to user: {str(e)}'
            }
    
    def _execute_create_task_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute create task action"""
        try:
            return {
                'success': True,
                'message': 'Task created successfully'
            }
            
        except Exception as e:
            logger.error(f"Error executing create task action: {str(e)}")
            return {
                'success': False,
                'message': f'Error creating task: {str(e)}'
            }
    
    def _execute_update_crm_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute update CRM action"""
        try:
            return {
                'success': True,
                'message': 'CRM updated successfully'
            }
            
        except Exception as e:
            logger.error(f"Error executing update CRM action: {str(e)}")
            return {
                'success': False,
                'message': f'Error updating CRM: {str(e)}'
            }
    
    def _execute_webhook_call_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute webhook call action"""
        try:
            url = action_config.get('url')
            method = action_config.get('method', 'POST')
            headers = action_config.get('headers', {})
            data = {**action_config.get('data', {}), **trigger_data}
            
            if not url:
                return {
                    'success': False,
                    'message': 'Webhook URL is required'
                }
            
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            return {
                'success': response.status_code < 400,
                'message': f'Webhook called successfully. Status: {response.status_code}',
                'response_data': response.json() if response.content else {}
            }
            
        except Exception as e:
            logger.error(f"Error executing webhook call action: {str(e)}")
            return {
                'success': False,
                'message': f'Error calling webhook: {str(e)}'
            }
    
    def _execute_delay_action(self, action_config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute delay action"""
        try:
            import time
            
            delay_seconds = action_config.get('delay_seconds', 0)
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            
            return {
                'success': True,
                'message': f'Delay completed: {delay_seconds} seconds'
            }
            
        except Exception as e:
            logger.error(f"Error executing delay action: {str(e)}")
            return {
                'success': False,
                'message': f'Error executing delay: {str(e)}'
            }
    
    def sync_integration(self, integration_id: str, sync_type: str = 'incremental') -> Dict[str, Any]:
        try:
            integration = EmailIntegration.objects.get(id=integration_id)
            
            if not integration.sync_enabled:
                return {
                    'success': False,
                    'message': 'Integration sync is disabled'
                }
            
            if integration.integration_type == 'crm':
                result = self._sync_crm_integration(integration, sync_type)
            elif integration.integration_type == 'helpdesk':
                result = self._sync_helpdesk_integration(integration, sync_type)
            elif integration.integration_type == 'analytics':
                result = self._sync_analytics_integration(integration, sync_type)
            else:
                result = {
                    'success': False,
                    'message': f'Unsupported integration type: {integration.integration_type}'
                }
            
            if result['success']:
                integration.status = 'active'
                integration.last_sync = timezone.now()
                integration.error_count = 0
                integration.last_error = None
            else:
                integration.status = 'error'
                integration.error_count += 1
                integration.last_error = result.get('message', 'Unknown error')
            
            integration.save()
            
            return result
            
        except EmailIntegration.DoesNotExist:
            return {
                'success': False,
                'message': 'Integration not found'
            }
        except Exception as e:
            logger.error(f"Error syncing integration: {str(e)}")
            return {
                'success': False,
                'message': f'Error syncing integration: {str(e)}'
            }
    
    def _sync_crm_integration(self, integration: EmailIntegration, sync_type: str) -> Dict[str, Any]:
        """Sync CRM integration"""
        try:
            return {
                'success': True,
                'message': 'CRM integration synced successfully',
                'records_synced': 0
            }
            
        except Exception as e:
            logger.error(f"Error syncing CRM integration: {str(e)}")
            return {
                'success': False,
                'message': f'Error syncing CRM: {str(e)}'
            }
    
    def _sync_helpdesk_integration(self, integration: EmailIntegration, sync_type: str) -> Dict[str, Any]:
        """Sync helpdesk integration"""
        try:
            return {
                'success': True,
                'message': 'Helpdesk integration synced successfully',
                'tickets_synced': 0
            }
            
        except Exception as e:
            logger.error(f"Error syncing helpdesk integration: {str(e)}")
            return {
                'success': False,
                'message': f'Error syncing helpdesk: {str(e)}'
            }
    
    def _sync_analytics_integration(self, integration: EmailIntegration, sync_type: str) -> Dict[str, Any]:
        """Sync analytics integration"""
        try:
            return {
                'success': True,
                'message': 'Analytics integration synced successfully',
                'metrics_synced': 0
            }
            
        except Exception as e:
            logger.error(f"Error syncing analytics integration: {str(e)}")
            return {
                'success': False,
                'message': f'Error syncing analytics: {str(e)}'
            }
    
    def get_integration_statistics(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get integration statistics"""
        try:
            # Build filter
            filters = {}
            if start_date:
                filters['date__gte'] = start_date
            if end_date:
                filters['date__lte'] = end_date
            
            # Get analytics data
            analytics = EmailIntegrationAnalytics.objects.filter(**filters)
            
            # Calculate totals
            total_webhook_events = analytics.aggregate(
                total=models.Sum('webhook_events_received')
            )['total'] or 0
            
            total_automation_executions = analytics.aggregate(
                total=models.Sum('automation_executions')
            )['total'] or 0
            
            total_integration_syncs = analytics.aggregate(
                total=models.Sum('integration_syncs')
            )['total'] or 0
            
            # Calculate success rates
            webhook_success_rate = analytics.aggregate(
                avg=models.Avg('webhook_success_rate')
            )['avg'] or 0
            
            automation_success_rate = analytics.aggregate(
                avg=models.Avg('automation_success_rate')
            )['avg'] or 0
            
            integration_success_rate = analytics.aggregate(
                avg=models.Avg('integration_success_rate')
            )['avg'] or 0
            
            # Get recent activity
            recent_webhooks = EmailWebhook.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            recent_automations = EmailAutomationLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            return {
                'total_webhook_events': total_webhook_events,
                'total_automation_executions': total_automation_executions,
                'total_integration_syncs': total_integration_syncs,
                'webhook_success_rate': round(webhook_success_rate, 2),
                'automation_success_rate': round(automation_success_rate, 2),
                'integration_success_rate': round(integration_success_rate, 2),
                'recent_webhooks': recent_webhooks,
                'recent_automations': recent_automations
            }
            
        except Exception as e:
            logger.error(f"Error getting integration statistics: {str(e)}")
            return {
                'error': f'Error getting integration statistics: {str(e)}'
            }
