import logging
import time
import requests
import json
from typing import List, Dict, Any, Optional, Type
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from cryptography.fernet import Fernet

from .models import (
    WhatsAppProvider,
    WhatsAppPhoneNumber,
    WhatsAppMessage,
    WhatsAppMessageTemplate,
    WhatsAppWebhookEvent,
    WhatsAppFlow,
    WhatsAppAccountHealthLog,
    WhatsAppAccountUsageLog,
)

logger = logging.getLogger(__name__)

class WhatsAppAPIError(Exception):
    """Custom exception for WhatsApp API errors"""
    pass
class BaseWhatsAppService:
   
    def __init__(self, provider_model: WhatsAppProvider):
        self.provider = provider_model
        self.encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
        
    def _decrypt(self, value: str) -> str:
        
        if not self.encryption_key or not value:
            return value
        try:
            fernet = Fernet(self.encryption_key.encode())
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    def _format_phone(self, phone_number: str) -> str:
       
        return str(phone_number).replace(" ", "").replace("-", "").replace("+", "")

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        raise NotImplementedError("This method must be implemented by a subclass")
        
    def send_template_message(self, to_phone: str, template: WhatsAppMessageTemplate, template_params: List[str], **kwargs) -> Dict:
        raise NotImplementedError("This method must be implemented by a subclass")

    def send_interactive_message(self, to_phone: str, flow: WhatsAppFlow, flow_token: str = None, **kwargs) -> Dict:
        raise NotImplementedError("This method must be implemented by a subclass")

    def handle_webhook(self, request_data: Dict) -> Any:
        raise NotImplementedError("This method must be implemented by a subclass")

    def health_check(self) -> Dict[str, Any]:
        raise NotImplementedError("This method must be implemented by a subclass")
        
    def _update_usage_counters(self, phone_number: Optional[WhatsAppPhoneNumber] = None):
        
        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            provider_to_update = WhatsAppProvider.objects.select_for_update().get(pk=self.provider.pk)

            if provider_to_update.last_reset_daily != today:
                provider_to_update.messages_sent_today = 0
                provider_to_update.last_reset_daily = today

            if provider_to_update.last_reset_monthly.month != today.month:
                provider_to_update.messages_sent_this_month = 0
                provider_to_update.last_reset_monthly = today

            provider_to_update.messages_sent_today = F('messages_sent_today') + 1
            provider_to_update.messages_sent_this_month = F('messages_sent_this_month') + 1
            provider_to_update.save(update_fields=[
                'messages_sent_today', 'messages_sent_this_month',
                'last_reset_daily', 'last_reset_monthly'
            ])

            if phone_number:
                phone_to_update = WhatsAppPhoneNumber.objects.select_for_update().get(pk=phone_number.pk)
                phone_to_update.messages_sent_today = F('messages_sent_today') + 1
                phone_to_update.messages_sent_this_month = F('messages_sent_this_month') + 1
                phone_to_update.last_message_sent = now
                phone_to_update.save(update_fields=[
                    'messages_sent_today', 'messages_sent_this_month', 'last_message_sent'
                ])

        usage_log, _ = WhatsAppAccountUsageLog.objects.get_or_create(
            provider=self.provider,
            date=today,
        )
        usage_log.messages_sent = F('messages_sent') + 1
        usage_log.save(update_fields=['messages_sent'])

class MetaProviderService(BaseWhatsAppService):
    
    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        self.api_version = provider_model.api_version or "v18.0"
        self.api_base_url = f"https://graph.facebook.com/{self.api_version}"
        
        self.access_token = self._decrypt(provider_model.access_token)
        self.phone_number_id = provider_model.phone_number_id
        self.business_account_id = provider_model.account_id

    def _format_phone(self, phone_number: str) -> str:
        clean_num = super()._format_phone(phone_number)
        if len(clean_num) == 10:
            return f"+91{clean_num}"
        if not clean_num.startswith('+'):
            return f"+{clean_num}"
        return clean_num

    def _make_api_request(self, url: str, method: str = 'GET', data: Dict = None) -> Dict[str, Any]:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise WhatsAppAPIError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = e.response.text if e.response else str(e)
            logger.error(f"Meta API request failed: {error_msg}")
            raise WhatsAppAPIError(f"API request failed: {error_msg}")

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        if not self.phone_number_id:
            raise WhatsAppAPIError("Meta provider is missing Phone Number ID.")
            
        url = f"{self.api_base_url}/{self.phone_number_id}/messages"
        data = {
            'messaging_product': 'whatsapp',
            'to': self._format_phone(to_phone),
            'type': 'text',
            'text': {'body': text_content}
        }
        
        try:
            response = self._make_api_request(url, 'POST', data)
            
            # Log the message
            phone_number = self.provider.get_primary_phone_number()
            WhatsAppMessage.objects.create(
                provider=self.provider,
                phone_number=phone_number,
                message_id=response['messages'][0]['id'],
                direction='outbound',
                message_type='text',
                to_phone_number=to_phone,
                from_phone_number=phone_number.phone_number if phone_number else '',
                content={'text': text_content},
                status='sent',
                sent_at=timezone.now(),
                customer_id=kwargs.get('customer_id'),
                campaign_id=kwargs.get('campaign_id')
            )
            self._update_usage_counters(phone_number)
            return response
        except Exception as e:
            logger.error(f"Failed to send Meta text message: {e}")
            raise WhatsAppAPIError(str(e))

    def send_template_message(self, to_phone: str, template: WhatsAppMessageTemplate, template_params: List[str], **kwargs) -> Dict:
        if not self.phone_number_id:
            raise WhatsAppAPIError("Meta provider is missing Phone Number ID.")

        url = f"{self.api_base_url}/{self.phone_number_id}/messages"
        data = {
            'messaging_product': 'whatsapp',
            'to': self._format_phone(to_phone),
            'type': 'template',
            'template': {
                'name': template.name,
                'language': {'code': template.language}
            }
        }
        
        if template_params:
            data['template']['components'] = [
                {
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': str(param) if param else ' '} for param in template_params]
                }
            ]
        
        try:
            response = self._make_api_request(url, 'POST', data)
            
            phone_number = self.provider.get_primary_phone_number()
            WhatsAppMessage.objects.create(
                provider=self.provider,
                phone_number=phone_number,
                message_id=response['messages'][0]['id'],
                direction='outbound',
                message_type='template',
                to_phone_number=to_phone,
                from_phone_number=phone_number.phone_number if phone_number else '',
                content={'template': template.name, 'params': template_params or []},
                template=template,
                status='sent',
                sent_at=timezone.now(),
                customer_id=kwargs.get('customer_id'),
                campaign_id=kwargs.get('campaign_id')
            )
            
            self._update_usage_counters(phone_number)
            template.usage_count = F('usage_count') + 1
            template.last_used = timezone.now()
            template.save(update_fields=['usage_count', 'last_used'])
            return response
            
        except Exception as e:
            logger.error(f"Failed to send Meta template message: {e}")
            raise WhatsAppAPIError(str(e))

    def health_check(self) -> Dict[str, Any]:
        if not self.access_token or not self.phone_number_id:
             return {'status': 'unhealthy', 'error': 'Missing Access Token or Phone Number ID'}

        try:
            url = f"{self.api_base_url}/{self.phone_number_id}"
            response = self._make_api_request(url, 'GET')
            
            health_status = 'healthy' if response.get('quality_rating') != 'LOW' else 'warning'
            check_details = {'api_response': response, 'checked_at': timezone.now().isoformat()}
            
            self.provider.last_health_check = timezone.now()
            self.provider.health_status = health_status
            self.provider.quality_rating = response.get('quality_rating', 'unknown').lower()
            self.provider.status = 'connected'
            self.provider.save(update_fields=['last_health_check', 'health_status', 'quality_rating', 'status'])
            
            WhatsAppAccountHealthLog.objects.create(
                provider=self.provider,
                health_status=health_status,
                check_details=check_details
            )
            return {'status': health_status, 'details': check_details}
            
        except Exception as e:
            self.provider.health_status = 'unhealthy'
            self.provider.status = 'disconnected'
            self.provider.save(update_fields=['health_status', 'status'])
            return {'status': 'unhealthy', 'error': str(e)}

    def handle_webhook(self, event_data: Dict[str, Any]) -> Any:
        pass


class TwilioProviderService(BaseWhatsAppService):

    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        self.account_sid = provider_model.account_id
        self.auth_token = self._decrypt(provider_model.access_token)
        self.from_number = provider_model.phone_number_id
        

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        logger.info(f"Sending Twilio message from {self.from_number} to {to_phone}")
        try:
            message_sid = f"tw_{int(time.time())}" 
            
            WhatsAppMessage.objects.create(
                provider=self.provider,
                message_id=message_sid,
                direction='outbound',
                message_type='text',
                to_phone_number=to_phone,
                from_phone_number=self.from_number,
                content={'text': text_content},
                status='sent',
                sent_at=timezone.now(),
                customer_id=kwargs.get('customer_id'),
                campaign_id=kwargs.get('campaign_id')
            )
            self._update_usage_counters()
            return {'messages': [{'id': message_sid}]}
        except Exception as e:
            logger.error(f"Failed to send Twilio message: {e}")
            raise WhatsAppAPIError(str(e))

    def send_template_message(self, to_phone: str, template: WhatsAppMessageTemplate, template_params: List[str], **kwargs) -> Dict:
        raise NotImplementedError("Twilio template sending not implemented yet.")

    def health_check(self) -> Dict[str, Any]:
        return {'status': 'healthy', 'details': 'Mock check passed'}

class GupshupProviderService(BaseWhatsAppService):
    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        self.api_key = self._decrypt(provider_model.access_token)
        self.app_name = provider_model.app_id
        self.source_number = provider_model.phone_number_id
        self.api_url = provider_model.api_url or "https://api.gupshup.io/wa/api/v1/msg"
        
        self.headers = {
            'Cache-Control': 'no-cache',
            'Content-Type': 'application/x-www-form-urlencoded',
            'apikey': self.api_key
        }

    def _make_api_request(self, payload: Dict) -> Dict[str, Any]:
        try:
            response = requests.post(self.api_url, headers=self.headers, data=payload, timeout=30)
            response.raise_for_status()
            resp_json = response.json()
            if resp_json.get('status') == 'error':
                raise WhatsAppAPIError(resp_json.get('message', 'Gupshup API error'))
            return resp_json
        except requests.exceptions.RequestException as e:
            logger.error(f"Gupshup API request failed: {e}")
            raise WhatsAppAPIError(f"API request failed: {str(e)}")

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        payload = {
            'channel': 'whatsapp',
            'source': self.source_number,
            'destination': self._format_phone(to_phone),
            'message': json.dumps({'type': 'text', 'text': text_content}),
            'src.name': self.app_name
        }
        
        response = self._make_api_request(payload)
        message_sid = response.get('messageId')
        
        WhatsAppMessage.objects.create(
            provider=self.provider,
            message_id=message_sid,
            direction='outbound',
            message_type='text',
            to_phone_number=to_phone,
            from_phone_number=self.source_number,
            content={'text': text_content},
            status='sent',
            sent_at=timezone.now(),
            customer_id=kwargs.get('customer_id'),
            campaign_id=kwargs.get('campaign_id')
        )
        self._update_usage_counters()
        return {'messages': [{'id': message_sid}]}

    def health_check(self) -> Dict[str, Any]:
        health_check_url = "https://api.gupshup.io/wa/api/v1/account/wallet/balance"
        try:
            response = requests.get(health_check_url, headers={'apikey': self.api_key}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success':
                self.provider.status = 'connected'
                self.provider.health_status = 'healthy'
                self.provider.save(update_fields=['status', 'health_status'])
                return {'status': 'healthy', 'details': data}
            else:
                raise WhatsAppAPIError(data.get('message'))
        except Exception as e:
            self.provider.health_status = 'unhealthy'
            self.provider.save(update_fields=['health_status'])
            return {'status': 'unhealthy', 'error': str(e)}


class Dialog360ProviderService(BaseWhatsAppService):
    
    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        # Map generic fields to 360Dialog requirements
        self.api_key = self._decrypt(provider_model.access_token)
        self.channel_id = provider_model.phone_number_id
        self.api_url = provider_model.api_url or "https://waba.360dialog.io/v1"
        
        self.headers = {
            'Content-Type': 'application/json',
            'D360-API-KEY': self.api_key
        }

    def _make_api_request(self, endpoint: str, payload: Dict) -> Dict[str, Any]:
        full_url = f"{self.api_url}/{endpoint}"
        try:
            response = requests.post(full_url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"360Dialog API request failed: {e}")
            raise WhatsAppAPIError(str(e))

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        payload = {
            "to": self._format_phone(to_phone),
            "type": "text",
            "text": {"body": text_content}
        }
        
        response = self._make_api_request("messages", payload)
        message_sid = response.get('messages', [{}])[0].get('id')
        
        WhatsAppMessage.objects.create(
            provider=self.provider,
            message_id=message_sid,
            direction='outbound',
            message_type='text',
            to_phone_number=to_phone,
            from_phone_number=self.channel_id,
            content={'text': text_content},
            status='sent',
            sent_at=timezone.now(),
            customer_id=kwargs.get('customer_id'),
            campaign_id=kwargs.get('campaign_id')
        )
        self._update_usage_counters()
        return {'messages': [{'id': message_sid}]}

    def health_check(self) -> Dict[str, Any]:
        health_check_url = f"{self.api_url}/health"
        try:
            response = requests.get(health_check_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('health') == 'green':
                self.provider.status = 'connected'
                self.provider.health_status = 'healthy'
                self.provider.save(update_fields=['status', 'health_status'])
                return {'status': 'healthy', 'details': data}
            else:
                raise WhatsAppAPIError(str(data))
        except Exception as e:
            self.provider.health_status = 'unhealthy'
            self.provider.save(update_fields=['health_status'])
            return {'status': 'unhealthy', 'error': str(e)}

class WhatsAppService:
   
    PROVIDER_MAP: Dict[str, Type[BaseWhatsAppService]] = {
        'meta': MetaProviderService,
        'twilio': TwilioProviderService,
        'gupshup': GupshupProviderService,
        '360dialog': Dialog360ProviderService,
    }

    def _get_provider_class(self, provider_type: str) -> Optional[Type[BaseWhatsAppService]]:
        return self.PROVIDER_MAP.get(provider_type)

    def get_service_instance(self, provider_id: int = None) -> BaseWhatsAppService:
        try:
            if provider_id:
                provider_model = WhatsAppProvider.objects.get(id=provider_id, is_active=True)
            else:
                provider_model = WhatsAppProvider.objects.get(is_default=True, is_active=True)
        
        except WhatsAppProvider.DoesNotExist:
            raise WhatsAppAPIError("No active or default WhatsApp provider found.")
        
        ProviderClass = self._get_provider_class(provider_model.provider_type)
        if not ProviderClass:
            raise WhatsAppAPIError(f"Provider type {provider_model.provider_type} is not supported.")
        
        return ProviderClass(provider_model)

    def get_service_instance_for_webhook(self, webhook_token: str = None, provider_id: int = None) -> BaseWhatsAppService:
        try:
            if provider_id:
                provider_model = WhatsAppProvider.objects.get(id=provider_id, is_active=True)
            elif webhook_token:
                provider_model = WhatsAppProvider.objects.get(webhook_verify_token=webhook_token, is_active=True)
            else:
                raise WhatsAppAPIError("Provider ID or Webhook Token is required.")
        except WhatsAppProvider.DoesNotExist:
            raise WhatsAppAPIError("Provider not found or not active.")
        
        ProviderClass = self._get_provider_class(provider_model.provider_type)
        return ProviderClass(provider_model)
    
    def get_analytics(self, provider: WhatsAppProvider, start_date=None, end_date=None) -> Dict[str, Any]:
        """Get analytics for a specific WABA account"""
        if not start_date:
            start_date = timezone.now().date() - timezone.timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        messages = WhatsAppMessage.objects.filter(
            provider=provider,
            created_at__date__range=[start_date, end_date]
        )
        
        total_messages = messages.count()
        sent_messages = messages.filter(direction='outbound').count()
        received_messages = messages.filter(direction='inbound').count()
        delivered_messages = messages.filter(status='delivered').count()
        read_messages = messages.filter(status='read').count()
        
        return {
            'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            'messages': {
                'total': total_messages,
                'sent': sent_messages,
                'received': received_messages,
                'delivered': delivered_messages,
                'read': read_messages
            }
        }