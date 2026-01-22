import logging
from typing import Dict, Any, Type, Optional
import boto3
import requests
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.conf import settings

from .models import SmsProvider, SmsMessage
from apps.billing.services import log_communication

logger = logging.getLogger(__name__)

class SmsApiException(Exception):
    """Custom exception for SMS API errors."""
    pass

class BaseSmsService:
    """
    Abstract base class for all SMS provider services.
    """
    def __init__(self, provider_model: SmsProvider):
        self.provider = provider_model
        # In a real implementation, you would decrypt credentials here
        self.credentials = provider_model.credentials

    def send_sms(self, to_phone: str, message: str, from_number: str = None, check_notifications: bool = False, **kwargs) -> Dict[str, Any]:
        """Send an SMS message."""
        raise NotImplementedError("This method must be implemented by a subclass.")

    def _is_sms_blocked(self, to_phone: str) -> bool:
        """Check if the user with this phone number has disabled SMS notifications."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(phone=to_phone, sms_notifications=False).exists()

    def _log_message(self, sid: str, to_phone: str, from_number: str, content: str, status: str, **kwargs):
        """Helper to log the sent message."""
        SmsMessage.objects.create(
            provider=self.provider,
            message_sid=sid,
            to_phone_number=to_phone,
            from_number=from_number,
            content=content,
            status=status,
            campaign=kwargs.get('campaign'),
            contact=kwargs.get('contact')
        )
        
        # --- BILLING INTEGRATION ---
        log_communication(
            vendor_name=self.provider.name,
            service_type='sms',
            customer=kwargs.get('customer'),
            case=kwargs.get('case'),
            status=status,
            cost=kwargs.get('cost'),
            message_snippet=content[:50] if content else "",
            error_message=kwargs.get('error_message'),
            provider_message_id=sid
        )

class TwilioSmsService(BaseSmsService):
    def send_sms(self, to_phone: str, message: str, from_number: str = None, check_notifications: bool = False, **kwargs) -> Dict[str, Any]:
        # --- REAL-TIME NOTIFICATION CHECK ---
        if check_notifications and self._is_sms_blocked(to_phone):
            logger.info(f"SMS blocked for {to_phone} due to user settings.")
            return {'sid': None, 'status': 'blocked', 'error': 'User disabled SMS notifications'}

        # Use the 'From' number from credentials if not provided
        sender = from_number or self.credentials.get('twilio_from_number')
        messaging_service_sid = self.credentials.get('twilio_messaging_service_sid')
        account_sid = self.credentials.get('twilio_account_sid')
        auth_token = self.credentials.get('twilio_auth_token')

        if not account_sid or not auth_token:
            raise SmsApiException("Twilio credentials (Account SID or Auth Token) are not configured.")

        try:
            client = Client(account_sid, auth_token)
            
            if messaging_service_sid:
                logger.info(f"Sending SMS via Twilio Messaging Service ({messaging_service_sid}) to {to_phone}")
                response = client.messages.create(body=message, messaging_service_sid=messaging_service_sid, to=to_phone)
            elif sender:
                logger.info(f"Sending SMS via Twilio from {sender} to {to_phone}")
                response = client.messages.create(body=message, from_=sender, to=to_phone)
            else:
                raise SmsApiException("Twilio provider requires a 'From Number' or a 'Messaging Service SID'.")

            # Try to capture cost if available
            cost = None
            if response.price:
                try:
                    cost = abs(float(response.price))
                except:
                    pass
            kwargs['cost'] = cost

            self._log_message(response.sid, to_phone, sender or messaging_service_sid, message, response.status, **kwargs)
            return {'sid': response.sid, 'status': response.status}
        except TwilioRestException as e:
            logger.error(f"Twilio API Error: {e}")
            self._log_message(f"failed-twilio-{to_phone}", to_phone, sender or messaging_service_sid or "unknown", message, 'failed', error_message=str(e), **kwargs)
            raise SmsApiException(f"Twilio Error: {e.msg}")

    def health_check(self):
        """Verifies Twilio credentials by fetching account info."""
        try:
            client = Client(self.credentials.get('twilio_account_sid'), self.credentials.get('twilio_auth_token'))
            client.api.v2010.accounts(self.credentials.get('twilio_account_sid')).fetch()
            return {'status': 'connected', 'details': 'Credentials valid'}
        except TwilioRestException as e:
            return {'status': 'disconnected', 'error': str(e)}
        except Exception as e:
            return {'status': 'disconnected', 'error': str(e)}

class Msg91SmsService(BaseSmsService):
    def send_sms(self, to_phone: str, message: str, from_number: str = None, check_notifications: bool = False, **kwargs) -> Dict[str, Any]:
        # --- REAL-TIME NOTIFICATION CHECK ---
        if check_notifications and self._is_sms_blocked(to_phone):
            logger.info(f"SMS blocked for {to_phone} due to user settings.")
            return {'sid': None, 'status': 'blocked', 'error': 'User disabled SMS notifications'}

        # 1. Get Credentials
        auth_key = self.credentials.get('msg91_auth_key')
        sender_id = self.credentials.get('msg91_sender_id')
        route = self.credentials.get('msg91_route', '4') # Default to transactional
        country = self.credentials.get('msg91_country_code', '91')
        
        if not auth_key or not sender_id:
            raise SmsApiException("MSG91 Auth Key or Sender ID missing.")

        # 2. Prepare Data
        # MSG91 V4 API URL
        url = "https://api.msg91.com/api/v2/sendsms"
        
        payload = {
            "sender": sender_id,
            "route": route,
            "country": country,
            "sms": [
                {
                    "message": message,
                    "to": [to_phone.replace('+', '')] # MSG91 prefers numbers without +
                }
            ]
        }
        
        headers = {
            'authkey': auth_key,
            'Content-Type': 'application/json'
        }

        try:
            logger.info(f"🚀 Sending Real MSG91 SMS to {to_phone}...")
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            resp_json = response.json()
            if resp_json.get('type') == 'error':
                raise Exception(resp_json.get('message'))

            request_id = resp_json.get('message') 
            self._log_message(request_id, to_phone, sender_id, message, 'sent', **kwargs)
            return {'sid': request_id, 'status': 'sent'}
        except Exception as e:
            logger.error(f"MSG91 Send Failed: {e}")
            self._log_message(f"failed-msg91-{to_phone}", to_phone, sender_id, message, 'failed', error_message=str(e), **kwargs)
            raise SmsApiException(str(e))

    def health_check(self):
        """Verifies MSG91 by checking balance (or just validating auth key)."""
        url = "https://api.msg91.com/api/balance.php"
        params = {"authkey": self.credentials.get('msg91_auth_key'), "type": "4"}
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200 and "error" not in response.text.lower():
                 return {'status': 'connected', 'details': f"Balance: {response.text}"}
            return {'status': 'disconnected', 'error': response.text}
        except Exception as e:
            return {'status': 'disconnected', 'error': str(e)}

class AwsSnsSmsService(BaseSmsService):
    def send_sms(self, to_phone: str, message: str, from_number: str = None, check_notifications: bool = False, **kwargs) -> Dict[str, Any]:
        # --- REAL-TIME NOTIFICATION CHECK ---
        if check_notifications and self._is_sms_blocked(to_phone):
            logger.info(f"SMS blocked for {to_phone} due to user settings.")
            return {'sid': None, 'status': 'blocked', 'error': 'User disabled SMS notifications'}

        # 1. Get Credentials
        access_key = self.credentials.get('aws_sns_access_key_id')
        secret_key = self.credentials.get('aws_sns_secret_access_key')
        region = self.credentials.get('aws_sns_region', 'us-east-1')
        
        if not access_key or not secret_key:
            raise SmsApiException("AWS Credentials missing.")

        try:
            # 2. Initialize Boto3 Client
            client = boto3.client(
                'sns',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )

            # 3. Send
            logger.info(f"🚀 Sending Real AWS SNS to {to_phone}...")
            response = client.publish(
                PhoneNumber=to_phone,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional' # Critical for OTPs/Alerts
                    }
                }
            )
            message_id = response['MessageId']
            self._log_message(message_id, to_phone, "AWS_SNS", message, 'sent', **kwargs)
            return {'sid': message_id, 'status': 'sent'}
        except Exception as e:
            logger.error(f"AWS SNS Failed: {e}")
            self._log_message(f"failed-aws-{to_phone}", to_phone, "AWS_SNS", message, 'failed', error_message=str(e), **kwargs)
            raise SmsApiException(str(e))

    def health_check(self):
        """Verifies AWS SNS access."""
        try:
            client = boto3.client(
                'sns',
                aws_access_key_id=self.credentials.get('aws_sns_access_key_id'),
                aws_secret_access_key=self.credentials.get('aws_sns_secret_access_key'),
                region_name=self.credentials.get('aws_sns_region', 'us-east-1')
            )
            # Try listing topics or getting SMS attributes to verify access
            client.get_sms_attributes()
            return {'status': 'connected', 'details': 'AWS Access Valid'}
        except Exception as e:
            return {'status': 'disconnected', 'error': str(e)}

class TextLocalSmsService(BaseSmsService):
    def send_sms(self, to_phone: str, message: str, from_number: str = None, check_notifications: bool = False, **kwargs) -> Dict[str, Any]:
        # --- REAL-TIME NOTIFICATION CHECK ---
        if check_notifications and self._is_sms_blocked(to_phone):
            logger.info(f"SMS blocked for {to_phone} due to user settings.")
            return {'sid': None, 'status': 'blocked', 'error': 'User disabled SMS notifications'}

        # 1. Get Credentials
        api_key = self.credentials.get('textlocal_api_key')
        sender = self.credentials.get('textlocal_sender', 'TXTLCL')
        
        if not api_key:
            raise SmsApiException("TextLocal API Key missing.")

        # 2. Prepare Data
        data = {
            'apikey': api_key,
            'numbers': to_phone.replace('+', ''), # TextLocal prefers no +
            'message': message,
            'sender': sender
        }

        try:
            logger.info(f"🚀 Sending Real TextLocal SMS to {to_phone}...")
            response = requests.post('https://api.textlocal.in/send/', data=data, timeout=10)
            resp_json = response.json()
            
            if resp_json.get('status') == 'success':
                batch_id = str(resp_json.get('batch_id'))
                self._log_message(batch_id, to_phone, sender, message, 'sent', **kwargs)
                return {'sid': batch_id, 'status': 'sent'}
            else:
                errors = resp_json.get('errors', [])
                error_msg = str(errors[0]['message']) if errors else "Unknown Error"
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"TextLocal Failed: {e}")
            self._log_message(f"failed-textlocal-{to_phone}", to_phone, sender, message, 'failed', error_message=str(e), **kwargs)
            raise SmsApiException(str(e))

    def health_check(self):
        """Verifies TextLocal by getting balance."""
        data = {'apikey': self.credentials.get('textlocal_api_key')}
        try:
            response = requests.post('https://api.textlocal.in/balance/', data=data, timeout=5)
            resp_json = response.json()
            if resp_json.get('status') == 'success':
                return {'status': 'connected', 'details': f"Credits: {resp_json.get('balance', {}).get('sms')}"}
            return {'status': 'disconnected', 'error': str(resp_json.get('errors'))}
        except Exception as e:
            return {'status': 'disconnected', 'error': str(e)}



class SmsService:
    """
    Factory class to get the correct SMS provider service.
    """
    PROVIDER_MAP: Dict[str, Type[BaseSmsService]] = {
        'twilio': TwilioSmsService,
        'msg91': Msg91SmsService,
        'aws_sns': AwsSnsSmsService,
        'textlocal': TextLocalSmsService,
    }

    def _get_provider_class(self, provider_type: str) -> Optional[Type[BaseSmsService]]:
        """Returns the correct service class based on the provider type."""
        return self.PROVIDER_MAP.get(provider_type)

    def get_service_instance(self, provider_id: int = None) -> BaseSmsService:
        """
        Gets an instance of the correct provider service.
        If provider_id is None, it fetches the 'default' provider.
        """
        try:
            if provider_id:
                provider_model = SmsProvider.objects.get(id=provider_id, is_active=True)
            else:
                logger.info("No provider ID given, fetching default SMS provider.")
                provider_model = SmsProvider.objects.get(is_default=True, is_active=True)

        except SmsProvider.DoesNotExist:
            logger.error(f"No active SMS provider found for ID: {provider_id} or as default.")
            raise SmsApiException("No active or default SMS provider configured.")
        except SmsProvider.MultipleObjectsReturned:
             logger.error("Multiple default SMS providers found. Please set only one default.")
             raise SmsApiException("Multiple default SMS providers found.")

        ProviderClass = self._get_provider_class(provider_model.provider_type)

        if not ProviderClass:
            logger.error(f"No service class found for SMS provider type: {provider_model.provider_type}")
            raise SmsApiException(f"Provider type {provider_model.provider_type} is not supported.")

        return ProviderClass(provider_model)