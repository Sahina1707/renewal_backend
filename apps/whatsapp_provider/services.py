#
# services.py
#
import logging
import time
import requests
import json
from typing import List, Dict, Any, Optional, Tuple, Type
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from apps.templates.models import Template
from .models import (
    WhatsAppProvider,  # Renamed
    WhatsAppPhoneNumber,
    WhatsAppMessage,
    WhatsAppMessageTemplate,
    WhatsAppWebhookEvent,
    WhatsAppFlow,
    WhatsAppAccountHealthLog,
    WhatsAppAccountUsageLog,
)

# You may need to install other SDKs
# pip install twilio
# from twilio.rest import Client
# from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# --- Helper function for encryption ---
def _encrypt_value(value: str) -> str:
    encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
    if not encryption_key or not value:
        logger.warning("Encrypt: No key or value, returning raw value.")
        return value
    try:
        fernet = Fernet(encryption_key.encode())
        return fernet.encrypt(value.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return value

# --- Helper function for decryption ---
def _decrypt_value(value: str) -> str:
    encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
    if not encryption_key or not value:
        return value
    try:
        fernet = Fernet(encryption_key.encode())
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return value # Return raw value if decryption fails

class WhatsAppAPIError(Exception):
    """Custom exception for WhatsApp API errors"""
    pass

# -----------------------------------------------------------------
# STEP 1: DEFINE THE BASE "INTERFACE"
# -----------------------------------------------------------------

class BaseWhatsAppService:
    """
    Abstract base class defining the interface for all WhatsApp providers.
    """
    def __init__(self, provider_model: WhatsAppProvider):
        self.provider = provider_model
        
        # Initialize encryption service
        self.encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
        self._fernet = None
        if self.encryption_key:
            try:
                self._fernet = Fernet(self.encryption_key.encode())
            except Exception as e:
                logger.error(f"Failed to initialize WhatsApp encryption: {e}")
        
        # Decrypt all credentials
        self.credentials = self._decrypt_credentials(provider_model.credentials)

    def _encrypt_credential(self, value: str) -> str:
        if not self._fernet or not value: return value
        try: return self._fernet.encrypt(value.encode()).decode()
        except: return value

    def _decrypt_credential(self, value: str) -> str:
        if not self._fernet or not value: return value
        try: return self._fernet.decrypt(value.encode()).decode()
        except: return value

    def _decrypt_credentials(self, credentials: Dict) -> Dict:
        """Decrypt all values in the credentials dictionary."""
        decrypted_creds = {}
        if not self._fernet:
            logger.warning("No encryption key set. Credentials are in plain text.")
            return credentials
            
        for key, value in credentials.items():
            if isinstance(value, str):
                try:
                    decrypted_creds[key] = self._decrypt_credential(value)
                except Exception:
                    logger.warning(f"Failed to decrypt credential key {key}, using raw value.")
                    decrypted_creds[key] = value
            else:
                decrypted_creds[key] = value
        return decrypted_creds

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        """Send a simple text message."""
        raise NotImplementedError("This method must be implemented by a subclass")
        
    def send_template_message(self, to_phone: str, template: WhatsAppMessageTemplate, template_params: List[str], **kwargs) -> Dict:
        """Send a template message."""
        raise NotImplementedError("This method must be implemented by a subclass")

    def send_interactive_message(self, to_phone: str, flow: WhatsAppFlow, flow_token: str = None, **kwargs) -> Dict:
        """Send an interactive message (WhatsApp Flow)."""
        raise NotImplementedError("This method must be implemented by a subclass")

    def handle_webhook(self, request_data: Dict) -> Any:
        """Process an incoming webhook event."""
        raise NotImplementedError("This method must be implemented by a subclass")

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the provider's API."""
        raise NotImplementedError("This method must be implemented by a subclass")
        
    def _update_usage_counters(self, phone_number: Optional[WhatsAppPhoneNumber] = None):
        """
        Atomically update usage counters for the provider and phone number
        to prevent race conditions.
        """
        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # Lock the provider row to prevent concurrent updates
            provider_to_update = WhatsAppProvider.objects.select_for_update().get(pk=self.provider.pk)

            # Reset daily counter if it's a new day
            if provider_to_update.last_reset_daily != today:
                provider_to_update.messages_sent_today = 0
                provider_to_update.last_reset_daily = today

            # Reset monthly counter if it's a new month
            if provider_to_update.last_reset_monthly.month != today.month:
                provider_to_update.messages_sent_this_month = 0
                provider_to_update.last_reset_monthly = today

            # Increment counters
            provider_to_update.messages_sent_today = F('messages_sent_today') + 1
            provider_to_update.messages_sent_this_month = F('messages_sent_this_month') + 1
            provider_to_update.save(update_fields=[
                'messages_sent_today', 'messages_sent_this_month',
                'last_reset_daily', 'last_reset_monthly'
            ])

            # Update Phone Number counters if provided
            if phone_number:
                # Lock the phone number row as well
                phone_to_update = WhatsAppPhoneNumber.objects.select_for_update().get(pk=phone_number.pk)
                phone_to_update.messages_sent_today = F('messages_sent_today') + 1
                phone_to_update.messages_sent_this_month = F('messages_sent_this_month') + 1
                phone_to_update.last_message_sent = now
                phone_to_update.save(update_fields=[
                    'messages_sent_today', 'messages_sent_this_month', 'last_message_sent'
                ])

        # Update daily usage log (get_or_create is atomic)
        usage_log, created = WhatsAppAccountUsageLog.objects.get_or_create(
            provider=self.provider,
            date=today,
        )
        usage_log.messages_sent = F('messages_sent') + 1
        usage_log.save(update_fields=['messages_sent'])
class MetaProviderService(BaseWhatsAppService):
    """
    Service for managing Meta (Facebook) Business API.
    """
    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        self.api_base_url = "https://graph.facebook.com/v18.0"
        self.access_token = self.credentials.get('meta_access_token')
        self.phone_number_id = self.credentials.get('meta_phone_number_id')

    def _format_phone(self, phone_number: str) -> str:
        clean_num = str(phone_number).replace(" ", "").replace("-", "").replace("+", "")
        if len(clean_num) == 10:
            return f"+91{clean_num}"
        if len(clean_num) > 10 and not str(phone_number).startswith('+'):
            return f"+{clean_num}"
        if not str(phone_number).startswith('+'):
            return f"+{phone_number}"
        return phone_number

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
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise WhatsAppAPIError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Meta API request failed: {e.response.reason} - {e.response.text}" if e.response else str(e)
            logger.error(error_msg)
            raise WhatsAppAPIError(f"API request failed: {error_msg}")

    def _prepare_template_params(self, contact: Any, template: WhatsAppMessageTemplate) -> List[str]:
        """
        Fixed Mapper: Guarantees no empty values are sent to Meta.
        """
        params = []
        # Define the exact keys your template needs.
        expected_keys = ['name', 'policy_number'] 

        print(f"🔥 DEBUG: Processing template '{template.name}'")

        for key in expected_keys:
            value = getattr(contact, key, None)
            
            # --- THE CRITICAL FIX ---
            # If value is missing, FORCE a fallback word.
            if not value or str(value).strip() == "" or str(value) == "None":
                if key == 'name':
                    value = "Valued Customer"
                elif key == 'policy_number':
                    value = "Renewal Pending"
                else:
                    value = "-" 
            
            params.append(str(value))
            
        print(f"🔥 DEBUG: Final Params sending to Meta: {params}")
        return params

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        if not self.phone_number_id:
            raise WhatsAppAPIError("Meta provider is not configured with a Phone Number ID.")
            
        url = f"{self.api_base_url}/{self.phone_number_id}/messages"
        data = {
            'messaging_product': 'whatsapp',
            'to': self._format_phone(to_phone),
            'type': 'text',
            'text': {'body': text_content}
        }
        
        try:
            response = self._make_api_request(url, 'POST', data)
            phone_number = self.provider.get_primary_phone_number()
            
            campaign_obj = kwargs.get('campaign')
            campaign_id = campaign_obj.id if campaign_obj and hasattr(campaign_obj, 'id') else None
            
            customer_obj = kwargs.get('customer')
            customer_id = customer_obj.id if customer_obj and hasattr(customer_obj, 'id') else None

            message = WhatsAppMessage.objects.create(
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
                customer_id=customer_id,
                campaign_id=campaign_id
            )
            self._update_usage_counters(phone_number)
            logger.info(f"Sent Meta text message to {to_phone}")
            return response
        except Exception as e:
            logger.error(f"Failed to send Meta text message: {e}")
            raise WhatsAppAPIError(str(e))

    def send_template_message(self, to_phone: str, template: WhatsAppMessageTemplate, template_params: List[str], **kwargs) -> Dict:
        if not self.phone_number_id:
            raise WhatsAppAPIError("Meta provider is not configured with a Phone Number ID.")

        # --- FORCE RE-MAPPING IF EMPTY ---
        contact = kwargs.get('customer')
        # We check if params look empty OR if they are ["", "None"]
        if contact and (not template_params or '' in template_params or 'None' in template_params):
             print("🔥 DEBUG: Detected empty parameters. Re-mapping now...")
             template_params = self._prepare_template_params(contact, template)

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
                    'parameters': [{'type': 'text', 'text': str(param) if param else ' '} 
                                   for param in template_params]
                }
            ]
        
        try:
            response = self._make_api_request(url, 'POST', data)
            phone_number = self.provider.get_primary_phone_number()

            campaign_obj = kwargs.get('campaign')
            campaign_id = campaign_obj.id if campaign_obj and hasattr(campaign_obj, 'id') else None
            
            customer_obj = kwargs.get('customer')
            customer_id = customer_obj.id if customer_obj and hasattr(customer_obj, 'id') else None

            message = WhatsAppMessage.objects.create(
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
                customer_id=customer_id,
                campaign_id=None # Keep this None to prevent DB crash
            )
            
            self._update_usage_counters(phone_number)
            template.usage_count = F('usage_count') + 1
            template.last_used = timezone.now()
            template.save(update_fields=['usage_count', 'last_used'])
            
            logger.info(f"Sent Meta template message {template.name} to {to_phone}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send Meta template message: {e}")
            raise WhatsAppAPIError(str(e))
    def send_interactive_message(self, to_phone: str, flow: WhatsAppFlow, flow_token: str = None, **kwargs) -> Dict:
        """Send an interactive message (WhatsApp Flow) via Meta Business API"""
        if not self.phone_number_id:
            raise WhatsAppAPIError("Meta provider is not configured with a Phone Number ID.")

        url = f"{self.api_base_url}/{self.phone_number_id}/messages"
        
        data = {
            'messaging_product': 'whatsapp',
            'to': self._format_phone(to_phone),
            'type': 'interactive',
            'interactive': {
                'type': 'flow',
                'body': {
                    'text': flow.description or 'Please complete this form:'
                },
                'action': {
                    'name': 'flow',
                    'parameters': {
                        'flow_message_version': '3',
                        'flow_token': flow_token or f"flow_token_{int(time.time())}",
                        'flow_id': flow.id, # Assuming flow.id is the Meta Flow ID
                        'flow_cta': 'Complete Form',
                        'flow_action_payload': {
                            'screen': 'SCREEN_NAME', # This might need to be dynamic
                            'data': {}
                        }
                    }
                }
            }
        }
        
        try:
            response = self._make_api_request(url, 'POST', data)
            phone_number = self.provider.get_primary_phone_number()

            message = WhatsAppMessage.objects.create(
                provider=self.provider,
                phone_number=phone_number,
                message_id=response['messages'][0]['id'],
                direction='outbound',
                message_type='interactive',
                to_phone_number=to_phone,
                from_phone_number=phone_number.phone_number if phone_number else '',
                content={'flow_id': flow.id, 'flow_token': flow_token},
                status='sent',
                sent_at=timezone.now(),
                customer=kwargs.get('customer'),
                campaign=kwargs.get('campaign')
            )
            
            self._update_usage_counters(phone_number)
            flow.usage_count = F('usage_count') + 1
            flow.last_used = timezone.now()
            flow.save(update_fields=['usage_count', 'last_used'])
            
            logger.info(f"Sent Meta interactive message {flow.name} to {to_phone}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send Meta interactive message: {e}")
            raise WhatsAppAPIError(str(e))

    def handle_webhook(self, event_data: Dict[str, Any]) -> Any:
        """Process incoming Meta webhook event"""
        try:
            event_type = self._determine_event_type(event_data)
            
            webhook_event = WhatsAppWebhookEvent.objects.create(
                provider=self.provider,
                event_type=event_type,
                raw_data=event_data
            )
            
            if event_type == 'message':
                self._process_incoming_message(webhook_event, event_data)
            elif event_type == 'message_status':
                self._process_message_status_update(webhook_event, event_data)
            elif event_type == 'account_update':
                self._process_account_update(webhook_event, event_data)
            elif event_type == 'template_status':
                self._process_template_status_update(webhook_event, event_data)
            
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=['processed', 'processed_at'])
            
            logger.info(f"Processed Meta webhook event {event_type} for provider {self.provider.name}")
            return webhook_event
            
        except Exception as e:
            logger.error(f"Failed to process Meta webhook event: {e}")
            if 'webhook_event' in locals():
                webhook_event.processing_error = str(e)
                webhook_event.save(update_fields=['processing_error'])
            raise

    def _determine_event_type(self, event_data: Dict[str, Any]) -> str:
        """Determine the type of webhook event from Meta"""
        # This logic is from your original file
        if 'messages' in event_data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}):
            return 'message'
        elif 'statuses' in event_data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}):
            return 'message_status'
        elif 'account_update' in event_data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}):
            return 'account_update'
        elif 'message_template_status_update' in event_data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}):
            return 'template_status'
        else:
            return 'unknown'

    def _process_incoming_message(self, webhook_event: WhatsAppWebhookEvent, event_data: Dict[str, Any]):
        """Process incoming message from customer"""
        value = event_data['entry'][0]['changes'][0]['value']
        metadata = value.get('metadata', {})
        phone_number_id = metadata.get('phone_number_id')
        
        try:
            phone_number = WhatsAppPhoneNumber.objects.get(
                provider=self.provider,
                phone_number_id=phone_number_id,
                is_active=True
            )
        except WhatsAppPhoneNumber.DoesNotExist:
            logger.warning(f"Phone number {phone_number_id} not found for provider {self.provider.name}")
            return

        for message_data in value.get('messages', []):
            try:
                WhatsAppMessage.objects.create(
                    provider=self.provider,
                    phone_number=phone_number,
                    message_id=message_data['id'],
                    direction='inbound',
                    message_type=message_data.get('type', 'text'),
                    to_phone_number=phone_number.phone_number,
                    from_phone_number=message_data['from'],
                    content=message_data,
                    status='delivered' # Inbound messages are already delivered
                )
                logger.info(f"Processed incoming message from {message_data['from']}")
            except Exception as e:
                logger.error(f"Failed to create incoming message record: {e}")

    def _process_message_status_update(self, webhook_event: WhatsAppWebhookEvent, event_data: Dict[str, Any]):
        """Process message status update (delivered, read, failed)"""
        value = event_data['entry'][0]['changes'][0]['value']
        for status_data in value.get('statuses', []):
            try:
                message_id = status_data['id']
                status = status_data['status']
                
                message = WhatsAppMessage.objects.get(message_id=message_id, provider=self.provider)
                message.status = status
                
                now = timezone.now()
                if status == 'delivered':
                    message.delivered_at = now
                elif status == 'read':
                    message.read_at = now
                elif status == 'failed':
                    message.error_code = status_data.get('errors', [{}])[0].get('code')
                    message.error_message = status_data.get('errors', [{}])[0].get('title')
                
                message.save()
                logger.info(f"Updated message {message_id} status to {status}")
            except WhatsAppMessage.DoesNotExist:
                logger.warning(f"Message {message_id} not found for status update")
            except Exception as e:
                logger.error(f"Failed to process status update: {e}")
    
    def _process_account_update(self, webhook_event: WhatsAppWebhookEvent, event_data: Dict[str, Any]):
        """Process account update events"""
        # (Logic from your original file)
        logger.info(f"Processing account update for provider {self.provider.name}")
        # Add logic to update self.provider.status, etc.

    def _process_template_status_update(self, webhook_event: WhatsAppWebhookEvent, event_data: Dict[str, Any]):
        """Process template status update events"""
        # (Logic from your original file)
        value = event_data['entry'][0]['changes'][0]['value']
        template_data = value.get('message_template_status_update', {})
        template_id = template_data.get('message_template_id')
        status = template_data.get('status')
        
        if template_id:
            try:
                template = WhatsAppMessageTemplate.objects.get(meta_template_id=template_id, provider=self.provider)
                template.status = 'approved' if status == 'APPROVED' else 'rejected'
                if status == 'REJECTED':
                    template.rejection_reason = template_data.get('reason', 'Unknown reason')
                template.save()
                logger.info(f"Updated template {template.name} status to {status}")
            except WhatsAppMessageTemplate.DoesNotExist:
                logger.warning(f"Template {template_id} not found for status update")

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Meta WABA account"""
        if not self.access_token or not self.phone_number_id:
             return {'status': 'unhealthy', 'error': 'Missing Access Token or Phone Number ID'}

        try:
            # Check phone number status
            url = f"{self.api_base_url}/{self.phone_number_id}"
            response = self._make_api_request(url, 'GET')
            
            health_status = 'healthy' if response.get('quality_rating') != 'LOW' else 'warning'
            check_details = {'api_response': response, 'checked_at': timezone.now().isoformat()}
            
            # Update provider health
            self.provider.last_health_check = timezone.now()
            self.provider.health_status = health_status
            self.provider.quality_rating = response.get('quality_rating', 'unknown').lower()
            self.provider.status = 'connected' # or 'verified'
            self.provider.save(update_fields=['last_health_check', 'health_status', 'quality_rating', 'status'])
            
            WhatsAppAccountHealthLog.objects.create(
                provider=self.provider,
                health_status=health_status,
                check_details=check_details
            )
            logger.info(f"Health check passed for Meta provider {self.provider.name}")
            return {'status': health_status, 'details': check_details}
            
        except Exception as e:
            health_status = 'unhealthy'
            error_message = str(e)
            
            self.provider.last_health_check = timezone.now()
            self.provider.health_status = health_status
            self.provider.status = 'disconnected'
            self.provider.save(update_fields=['last_health_check', 'health_status', 'status'])
            
            WhatsAppAccountHealthLog.objects.create(
                provider=self.provider,
                health_status=health_status,
                check_details={'error': error_message},
                error_message=error_message
            )
            logger.error(f"Health check failed for Meta provider {self.provider.name}: {e}")
            return {'status': health_status, 'error': error_message}


class TwilioProviderService(BaseWhatsAppService):
    """
    Service for managing Twilio WhatsApp API.
    """
    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        # try:
        #     self.client = Client(
        #         self.credentials.get('twilio_account_sid'),
        #         self.credentials.get('twilio_auth_token')
        #     )
        #     self.from_number = self.credentials.get('twilio_from_number')
        # except Exception as e:
        #     logger.error(f"Failed to initialize Twilio client: {e}")
        #     raise WhatsAppAPIError("Twilio credentials missing or invalid.")
        logger.info("Twilio Service Initialized (Mock)")
        self.from_number = self.credentials.get('twilio_from_number', 'fake-twilio-num')


    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        """Send a text message via Twilio API (Mock)"""
        logger.info(f"Sending Twilio message to {to_phone}")
        try:
            # MOCK IMPLEMENTATION
            # message = self.client.messages.create(
            #     body=text_content,
            #     from_=f'whatsapp:{self.from_number}',
            #     to=f'whatsapp:{to_phone}'
            # )
            # message_sid = message.sid
            message_sid = f"fake_twilio_sid_{int(time.time())}" # Placeholder
            
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
                customer=kwargs.get('customer'),
                campaign=kwargs.get('campaign')
            )
            self._update_usage_counters()
            return {'messages': [{'id': message_sid}]} # Mocking Meta's response structure
        except Exception as e:
            logger.error(f"Failed to send Twilio message: {e}")
            raise WhatsAppAPIError(str(e))

    def send_template_message(self, to_phone: str, template: WhatsAppMessageTemplate, template_params: List[str], **kwargs) -> Dict:
        raise NotImplementedError("Twilio template messages not yet implemented.")

    def send_interactive_message(self, to_phone: str, flow: WhatsAppFlow, flow_token: str = None, **kwargs) -> Dict:
        raise NotImplementedError("Twilio interactive messages not yet implemented.")

    def handle_webhook(self, request_data: Dict) -> Any:
        logger.info(f"Processing Twilio webhook for provider: {self.provider.name}")
        # Add logic to parse Twilio's webhook format
        pass

    def health_check(self) -> Dict[str, Any]:
        logger.info(f"Health check for Twilio provider: {self.provider.name}")
        # try:
        #     self.client.api.v2010.accounts(self.credentials.get('twilio_account_sid')).fetch()
        #     return {'status': 'healthy'}
        # except Exception as e:
        #     return {'status': 'unhealthy', 'error': str(e)}
        return {'status': 'healthy'}

class GupshupProviderService(BaseWhatsAppService):
    """
    Service for managing Gupshup WhatsApp API.
    (Now with real implementation)
    """
    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        try:
            self.api_key = self.credentials.get('gupshup_api_key')
            self.app_name = self.credentials.get('gupshup_app_name')
            self.source_number = self.credentials.get('gupshup_source_number')
            
            # Use the stored URL or a default
            self.api_url = self.credentials.get('gupshup_api_url')
            if not self.api_url:
                # Default Gupshup v1 API URL
                self.api_url = "https://api.gupshup.io/wa/api/v1/msg"
                
            if not all([self.api_key, self.app_name, self.source_number]):
                raise WhatsAppAPIError("Gupshup credentials missing or invalid.")
                
            self.headers = {
                'Cache-Control': 'no-cache',
                'Content-Type': 'application/x-www-form-urlencoded',
                'apikey': self.api_key
            }
        except Exception as e:
            logger.error(f"Failed to initialize Gupshup client: {e}")
            raise WhatsAppAPIError("Gupshup credentials missing or invalid.")

    def _format_phone(self, phone_number: str) -> str:
        """Helper to clean Gupshup numbers (they don't use '+')."""
        return str(phone_number).replace(" ", "").replace("-", "").replace("+", "")

    def _make_api_request(self, payload: Dict) -> Dict[str, Any]:
        """Make API request to Gupshup."""
        try:
            response = requests.post(self.api_url, headers=self.headers, data=payload, timeout=30)
            response.raise_for_status()
            
            resp_json = response.json()
            if resp_json.get('status') == 'error':
                raise WhatsAppAPIError(resp_json.get('message', 'Gupshup API error'))
                
            return resp_json
        except requests.exceptions.RequestException as e:
            logger.error(f"Gupshup API request failed: {e.response.text if e.response else e}")
            raise WhatsAppAPIError(f"API request failed: {str(e)}")

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        """Send a text message via Gupshup API"""
        logger.info(f"Sending Gupshup text message to {to_phone}")
        
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
            customer=kwargs.get('customer'),
            campaign=kwargs.get('campaign')
        )
        self._update_usage_counters()
        return {'messages': [{'id': message_sid}]}

    def send_template_message(self, to_phone: str, template: Template, template_params: List[str], **kwargs) -> Dict:
        """Send a template message via Gupshup API"""
        logger.info(f"Sending Gupshup template {template.name} to {to_phone}")
        
        # Gupshup template ID is stored in 'dlt_template_id'
        template_id = template.dlt_template_id
        if not template_id:
            raise WhatsAppAPIError(f"Template '{template.name}' is missing its Gupshup Template ID.")

        # Build the message payload for a template
        message_payload = {
            "type": "template",
            "id": template_id,
            "params": template_params
        }
        
        payload = {
            'channel': 'whatsapp',
            'source': self.source_number,
            'destination': self._format_phone(to_phone),
            'message': json.dumps(message_payload),
            'src.name': self.app_name
        }
        
        response = self._make_api_request(payload)
        message_sid = response.get('messageId')

        # Log this send to the WhatsAppMessage table
        phone_number_obj = self.provider.get_primary_phone_number()
        WhatsAppMessage.objects.create(
            provider=self.provider,
            phone_number=phone_number_obj,
            message_id=message_sid,
            direction='outbound',
            message_type='template',
            to_phone_number=to_phone,
            from_phone_number=self.source_number,
            content={'template': template.name, 'params': template_params},
            template=template,
            status='sent',
            sent_at=timezone.now(),
            customer=kwargs.get('customer'),
            campaign=kwargs.get('campaign')
        )
        
        self._update_usage_counters(phone_number_obj)
        template.usage_count = F('usage_count') + 1
        template.last_used = timezone.now()
        template.save(update_fields=['usage_count', 'last_used'])

        return {'messages': [{'id': message_sid}]}

    def send_interactive_message(self, to_phone: str, flow: WhatsAppFlow, flow_token: str = None, **kwargs) -> Dict:
        raise NotImplementedError("Gupshup interactive messages not yet implemented.")

    def handle_webhook(self, request_data: Dict) -> Any:
        logger.info(f"Processing Gupshup webhook for provider: {self.provider.name}")
        # Add logic to parse Gupshup's webhook format
        pass

    def health_check(self) -> Dict[str, Any]:
        """Performs a health check on the Gupshup account."""
        logger.info(f"Health check for Gupshup provider: {self.provider.name}")
        
        # We will try to get the account's wallet balance as a health check
        health_check_url = "https://api.gupshup.io/wa/api/v1/account/wallet/balance"
        try:
            response = requests.get(health_check_url, headers={'apikey': self.api_key}, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'success':
                self.provider.status = 'connected'
                self.provider.health_status = 'healthy'
                self.provider.last_health_check = timezone.now()
                self.provider.save(update_fields=['status', 'health_status', 'last_health_check'])
                return {'status': 'healthy', 'details': data}
            else:
                raise WhatsAppAPIError(data.get('message', 'Gupshup health check failed'))

        except (requests.exceptions.RequestException, WhatsAppAPIError) as e:
            logger.error(f"Gupshup health check FAILED: {e}")
            self.provider.status = 'disconnected'
            self.provider.health_status = 'unhealthy'
            self.provider.last_health_check = timezone.now()
            self.provider.save(update_fields=['status', 'health_status', 'last_health_check'])
            return {'status': 'unhealthy', 'error': str(e)}

class Dialog360ProviderService(BaseWhatsAppService):
    """
    Service for managing 360Dialog WhatsApp API.
    (Now with real implementation)
    """
    def __init__(self, provider_model: WhatsAppProvider):
        super().__init__(provider_model)
        try:
            self.api_key = self.credentials.get('dialog_api_key')
            self.channel_id = self.credentials.get('dialog_channel_id')
            
            # 360Dialog API URL
            self.api_url = "https://waba.360dialog.io/v1" 
                
            if not all([self.api_key, self.channel_id]):
                raise WhatsAppAPIError("360Dialog credentials (API Key, Channel ID) missing or invalid.")
                
            self.headers = {
                'Content-Type': 'application/json',
                'D360-API-KEY': self.api_key
            }
        except Exception as e:
            logger.error(f"Failed to initialize 360Dialog client: {e}")
            raise WhatsAppAPIError("360Dialog credentials missing or invalid.")

    def _format_phone(self, phone_number: str) -> str:
        """Helper to clean 360Dialog numbers (they don't use '+')."""
        return str(phone_number).replace(" ", "").replace("-", "").replace("+", "")

    def _make_api_request(self, endpoint: str, payload: Dict) -> Dict[str, Any]:
        """Make API request to 360Dialog."""
        full_url = f"{self.api_url}/{endpoint}"
        try:
            response = requests.post(full_url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            
            resp_json = response.json()
            # 360Dialog doesn't have a top-level 'status' field, check for errors differently
            if response.status_code >= 400:
                 raise WhatsAppAPIError(resp_json.get('meta', {}).get('message', '360Dialog API error'))
                
            return resp_json
        except requests.exceptions.RequestException as e:
            logger.error(f"360Dialog API request failed: {e.response.text if e.response else e}")
            raise WhatsAppAPIError(f"API request failed: {str(e)}")

    def send_text_message(self, to_phone: str, text_content: str, **kwargs) -> Dict:
        """Send a text message via 360Dialog API"""
        logger.info(f"Sending 360Dialog text message to {to_phone}")
        
        payload = {
            "to": self._format_phone(to_phone),
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text_content
            }
        }
        
        response = self._make_api_request("messages", payload)
        message_sid = response.get('messages', [{}])[0].get('id')
        
        WhatsAppMessage.objects.create(
            provider=self.provider,
            message_id=message_sid,
            direction='outbound',
            message_type='text',
            to_phone_number=to_phone,
            from_phone_number=self.channel_id, # Use Channel ID as 'from'
            content={'text': text_content},
            status='sent',
            sent_at=timezone.now(),
            customer=kwargs.get('customer'),
            campaign=kwargs.get('campaign')
        )
        self._update_usage_counters()
        return {'messages': [{'id': message_sid}]}

    def send_template_message(self, to_phone: str, template: Template, template_params: List[str], **kwargs) -> Dict:
        """Send a template message via 360Dialog API"""
        logger.info(f"Sending 360Dialog template {template.name} to {to_phone}")
        
        # 360Dialog uses the template name, not an ID
        template_name = template.name 
        
        # Build components
        components = []
        if template_params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": param} for param in template_params]
            })

        payload = {
            "to": self._format_phone(to_phone),
            "type": "template",
            "template": {
                "namespace": self.channel_id, # Namespace is usually the Channel ID
                "name": template_name,
                "language": {
                    "policy": "deterministic",
                    "code": template.language
                },
                "components": components if components else []
            }
        }
        
        response = self._make_api_request("messages", payload)
        message_sid = response.get('messages', [{}])[0].get('id')

        # Log this send to the WhatsAppMessage table
        phone_number_obj = self.provider.get_primary_phone_number()
        WhatsAppMessage.objects.create(
            provider=self.provider,
            phone_number=phone_number_obj,
            message_id=message_sid,
            direction='outbound',
            message_type='template',
            to_phone_number=to_phone,
            from_phone_number=self.channel_id,
            content={'template': template.name, 'params': template_params},
            template=template,
            status='sent',
            sent_at=timezone.now(),
            customer=kwargs.get('customer'),
            campaign=kwargs.get('campaign')
        )
        
        self._update_usage_counters(phone_number_obj)
        template.usage_count = F('usage_count') + 1
        template.last_used = timezone.now()
        template.save(update_fields=['usage_count', 'last_used'])

        return {'messages': [{'id': message_sid}]}

    def send_interactive_message(self, to_phone: str, flow: WhatsAppFlow, flow_token: str = None, **kwargs) -> Dict:
        raise NotImplementedError("360Dialog interactive messages not yet implemented.")

    def handle_webhook(self, request_data: Dict) -> Any:
        logger.info(f"Processing 360Dialog webhook for provider: {self.provider.name}")
        # Add logic to parse 360Dialog's webhook format
        pass

    def health_check(self) -> Dict[str, Any]:
        """Performs a health check on the 360Dialog account."""
        logger.info(f"Health check for 360Dialog provider: {self.provider.name}")
        
        # We will try to get the channel health status
        health_check_url = f"{self.api_url}/health"
        try:
            response = requests.get(health_check_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('health') == 'green':
                self.provider.status = 'connected'
                self.provider.health_status = 'healthy'
                self.provider.last_health_check = timezone.now()
                self.provider.save(update_fields=['status', 'health_status', 'last_health_check'])
                return {'status': 'healthy', 'details': data}
            else:
                raise WhatsAppAPIError(data.get('details', '360Dialog health check returned not-green status'))

        except (requests.exceptions.RequestException, WhatsAppAPIError) as e:
            logger.error(f"360Dialog health check FAILED: {e}")
            self.provider.status = 'disconnected'
            self.provider.health_status = 'unhealthy'
            self.provider.last_health_check = timezone.now()
            self.provider.save(update_fields=['status', 'health_status', 'last_health_check'])
            return {'status': 'unhealthy', 'error': str(e)}
class WhatsAppService:
    """
    Factory class to get the correct provider service.
    This is the main entry point for other apps.
    """
    
    PROVIDER_MAP: Dict[str, Type[BaseWhatsAppService]] = {
        'meta': MetaProviderService,
        'twilio': TwilioProviderService,
        'gupshup': GupshupProviderService,
        '360dialog': Dialog360ProviderService,
    }

    def _get_provider_class(self, provider_type: str) -> Optional[Type[BaseWhatsAppService]]:
        """Returns the correct service class based on the provider type."""
        return self.PROVIDER_MAP.get(provider_type)

    def get_service_instance(self, provider_id: int = None) -> BaseWhatsAppService:
        """
        Gets an instance of the correct provider service.
        If provider_id is None, it fetches the 'default' provider.
        """
        try:
            if provider_id:
                provider_model = WhatsAppProvider.objects.get(id=provider_id, is_active=True)
            else:
                logger.info("No provider ID given, fetching default provider.")
                provider_model = WhatsAppProvider.objects.get(is_default=True, is_active=True)
        
        except WhatsAppProvider.DoesNotExist:
            logger.error(f"No active WhatsApp provider found for ID: {provider_id} or as default.")
            raise WhatsAppAPIError("No active or default WhatsApp provider configured.")
        except WhatsAppProvider.MultipleObjectsReturned:
             logger.error("Multiple default providers found. Please set only one default.")
             raise WhatsAppAPIError("Multiple default providers found. Please set only one default.")
        
        ProviderClass = self._get_provider_class(provider_model.provider_type)
        
        if not ProviderClass:
            logger.error(f"No service class found for provider type: {provider_model.provider_type}")
            raise WhatsAppAPIError(f"Provider type {provider_model.provider_type} is not supported.")
        
        # Return an *instance* of the correct service class, e.g., MetaProviderService(provider_model)
        return ProviderClass(provider_model)

    def get_service_instance_for_webhook(self, webhook_token: str = None, provider_id: int = None) -> BaseWhatsAppService:
        """
        Gets a service instance specifically for an incoming webhook.
        It finds the provider based on ID (from URL) or a verify token.
        """
        try:
            provider_model = None
            if provider_id:
                provider_model = WhatsAppProvider.objects.get(id=provider_id, is_active=True)
            elif webhook_token:
                # This is a fallback if the ID isn't in the URL
                # Note: This assumes webhook_verify_token is unique
                provider_model = WhatsAppProvider.objects.get(webhook_verify_token=webhook_token, is_active=True)
            else:
                raise WhatsAppAPIError("Provider ID or Webhook Token is required.")

        except WhatsAppProvider.DoesNotExist:
            logger.error(f"Webhook received for unknown provider (ID: {provider_id}, Token: {webhook_token})")
            raise WhatsAppAPIError("Provider not found or not active.")
        
        ProviderClass = self._get_provider_class(provider_model.provider_type)
        if not ProviderClass:
            raise WhatsAppAPIError(f"Provider type {provider_model.provider_type} is not supported.")
        
        return ProviderClass(provider_model)

    def get_analytics(self, provider: WhatsAppProvider, start_date=None, end_date=None) -> Dict[str, Any]:
        """Get analytics for a specific WABA account"""
        # This logic is from your original file, just adapted to take a provider object
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
        failed_messages = messages.filter(status='failed').count()
        
        template_usage = {}
        for template in provider.message_templates.filter(status='approved'):
            usage_count = messages.filter(template=template).count()
            if usage_count > 0:
                template_usage[template.name] = usage_count
        
        return {
            'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            'messages': {
                'total': total_messages, 'sent': sent_messages, 'received': received_messages,
                'delivered': delivered_messages, 'read': read_messages, 'failed': failed_messages
            },
            'delivery_rate': (delivered_messages / sent_messages * 100) if sent_messages > 0 else 0,
            'read_rate': (read_messages / delivered_messages * 100) if delivered_messages > 0 else 0,
            'template_usage': template_usage
        }