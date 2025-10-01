import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from cryptography.fernet import Fernet
import json
import requests
import boto3
from botocore.exceptions import ClientError
import ssl
import urllib3
import time

# Disable SSL verification globally for SendGrid
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .models import EmailProviderConfig, EmailProviderHealthLog, EmailProviderUsageLog

logger = logging.getLogger(__name__)


class EmailProviderService:
    """Service for managing email providers and sending emails"""
    
    def __init__(self):
        self.encryption_key = getattr(settings, 'EMAIL_PROVIDER_ENCRYPTION_KEY', None)
        self._fernet = None
        if self.encryption_key:
            try:
                self._fernet = Fernet(self.encryption_key.encode())
            except Exception as e:
                logger.error(f"Failed to initialize encryption: {e}")
    
    def _encrypt_credential(self, value: str) -> str:
        """Encrypt a credential value"""
        if not self._fernet or not value:
            return value
        try:
            return self._fernet.encrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt credential: {e}")
            return value
    
    def _decrypt_credential(self, value: str) -> str:
        """Decrypt a credential value"""
        if not self._fernet or not value:
            return value
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt credential: {e}")
            return value
    
    def get_active_providers(self) -> List[EmailProviderConfig]:
        """Get all active email providers ordered by priority"""
        return EmailProviderConfig.objects.filter(
            is_active=True,
            is_deleted=False
        ).order_by('priority', 'name')
    
    def get_healthy_providers(self) -> List[EmailProviderConfig]:
        """Get all healthy and active email providers"""
        return EmailProviderConfig.objects.filter(
            is_active=True,
            is_deleted=False,
            health_status='healthy'
        ).order_by('priority', 'name')
    
    def get_available_provider(self) -> Optional[EmailProviderConfig]:
        """Get the first available provider that can send emails"""
        # First try healthy providers
        providers = self.get_healthy_providers()
        
        for provider in providers:
            if provider.can_send_email():
                return provider
        
        # If no healthy providers, try active providers with unknown health status
        # This is useful for providers that haven't been health-checked yet
        active_providers = EmailProviderConfig.objects.filter(
            is_active=True,
            is_deleted=False,
            health_status__in=['unknown', 'healthy']
        ).order_by('priority', 'name')
        
        for provider in active_providers:
            # For unknown health status, check basic requirements
            if (provider.api_key and 
                provider.provider_type == 'sendgrid' and 
                provider.from_email):
                logger.info(f"Using provider with unknown health status: {provider.name}")
                return provider
        
        return None
    
    def send_email(self, to_emails: List[str], subject: str, html_content: str = '',
                   text_content: str = '', from_email: str = None, from_name: str = None,
                   reply_to: str = None, cc_emails: List[str] = None,
                   bcc_emails: List[str] = None, attachments: List[Tuple[str, str, str]] = None,
                   custom_args: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Send email using the best available provider
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content of the email
            from_email: Sender email address
            from_name: Sender name
            reply_to: Reply-to email address
            cc_emails: List of CC email addresses
            bcc_emails: List of BCC email addresses
            attachments: List of tuples (filename, content, mimetype)
        
        Returns:
            Dict with success status, provider info, and response details
        """
        provider = self.get_available_provider()
        
        if not provider:
            return {
                'success': False,
                'error': 'No available email providers',
                'provider_name': None
            }
        
        start_time = time.time()
        
        try:
            if provider.provider_type == 'sendgrid':
                result = self._send_via_sendgrid(provider, to_emails, subject, html_content,
                                               text_content, from_email, from_name, reply_to,
                                               cc_emails, bcc_emails, attachments, custom_args)
            elif provider.provider_type == 'aws_ses':
                result = self._send_via_aws_ses(provider, to_emails, subject, html_content,
                                              text_content, from_email, from_name, reply_to,
                                              cc_emails, bcc_emails, attachments)
            elif provider.provider_type == 'smtp':
                result = self._send_via_smtp(provider, to_emails, subject, html_content,
                                           text_content, from_email, from_name, reply_to,
                                           cc_emails, bcc_emails, attachments)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported provider type: {provider.provider_type}',
                    'provider_name': provider.name
                }
            
            response_time = time.time() - start_time
            
            # Log usage
            self._log_usage(provider, len(to_emails), result['success'], response_time)
            
            # Update provider usage
            if result['success']:
                provider.increment_usage(len(to_emails))
            
            result['response_time'] = response_time
            result['provider_name'] = provider.name
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending email via {provider.name}: {str(e)}")
            response_time = time.time() - start_time
            
            # Log failed usage
            self._log_usage(provider, len(to_emails), False, response_time)
            
            return {
                'success': False,
                'error': str(e),
                'provider_name': provider.name,
                'response_time': response_time
            }
    
    def _send_via_sendgrid(self, provider: EmailProviderConfig, to_emails: List[str],
                          subject: str, html_content: str, text_content: str,
                          from_email: str, from_name: str, reply_to: str,
                          cc_emails: List[str], bcc_emails: List[str],
                          attachments: List[Tuple[str, str, str]],
                          custom_args: Dict[str, str] = None) -> Dict[str, Any]:
        """Send email via SendGrid"""
        try:
            api_key = self._decrypt_credential(provider.api_key)
            if not api_key:
                raise ValueError("SendGrid API key not configured")
            
            sg = SendGridAPIClient(api_key=api_key)
            
            # Prepare email
            from_email_addr = from_email or provider.from_email
            from_name_str = from_name or provider.from_name or ""
            
            # Debug logging
            logger.info(f"SendGrid sending email from: {from_email_addr} with name: {from_name_str}")
            logger.info(f"SendGrid sending to: {to_emails}")
            logger.info(f"SendGrid subject: {subject}")
            
            mail = Mail(
                from_email=(from_email_addr, from_name_str),
                to_emails=to_emails,
                subject=subject,
                html_content=html_content,
                plain_text_content=text_content
            )
            
            if reply_to:
                mail.reply_to = reply_to
            elif provider.reply_to:
                mail.reply_to = provider.reply_to
            
            if cc_emails:
                mail.cc = cc_emails
            
            if bcc_emails:
                mail.bcc = bcc_emails
            
            # Add custom arguments for webhook tracking (using proper SendGrid syntax)
            if custom_args:
                from sendgrid.helpers.mail import CustomArg
                for key, value in custom_args.items():
                    mail.add_custom_arg(CustomArg(key, value))
                logger.info(f"Added custom_args to SendGrid email: {custom_args}")
            
            # Enable SendGrid click and open tracking (using proper SendGrid classes)
            from sendgrid.helpers.mail import ClickTracking, OpenTracking, TrackingSettings
            tracking_settings = TrackingSettings()
            tracking_settings.click_tracking = ClickTracking(enable=True, enable_text=True)
            tracking_settings.open_tracking = OpenTracking(enable=True)
            mail.tracking_settings = tracking_settings
            
            # Add attachments
            if attachments:
                for filename, content, mimetype in attachments:
                    mail.add_attachment(content, mimetype, filename)
            
            # Send email
            response = sg.send(mail)
            
            return {
                'success': True,
                'message_id': response.headers.get('X-Message-Id'),
                'status_code': response.status_code
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"SendGrid error: {error_msg}")
            
            # Try to get more detailed error information
            if hasattr(e, 'body'):
                try:
                    import json
                    error_details = json.loads(e.body)
                    error_msg = f"{error_msg} - Details: {error_details}"
                except:
                    pass
        
            if "does not match a verified Sender Identity" in error_msg:
          
                helpful_error = f"""
SendGrid Error: The sender email '{from_email}' is not verified in your SendGrid account.

To fix this issue:
1. Go to SendGrid Dashboard → Settings → Sender Authentication
2. Verify the email '{from_email}' as a Single Sender
3. Or set up Domain Authentication for your domain
4. Or use a different verified email address

Current SendGrid provider: {provider.name}
Provider from_email: {provider.from_email}

For more help, visit: https://sendgrid.com/docs/for-developers/sending-email/sender-identity/
                """.strip()
                
                return {
                    'success': False,
                    'error': helpful_error,
                    'error_type': 'sender_identity_not_verified',
                    'suggested_action': 'verify_sender_identity'
                }
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _send_via_aws_ses(self, provider: EmailProviderConfig, to_emails: List[str],
                         subject: str, html_content: str, text_content: str,
                         from_email: str, from_name: str, reply_to: str,
                         cc_emails: List[str], bcc_emails: List[str],
                         attachments: List[Tuple[str, str, str]]) -> Dict[str, Any]:
        """Send email via AWS SES"""
        try:
            access_key = self._decrypt_credential(provider.access_key_id)
            secret_key = self._decrypt_credential(provider.secret_access_key)
            
            if not access_key or not secret_key:
                raise ValueError("AWS SES credentials not configured")
            
            logger.info(f"AWS SES: Sending email via provider '{provider.name}' to {len(to_emails)} recipient(s)")
            
            # Initialize SES client
            ses_client = boto3.client(
                'ses',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=provider.aws_region or getattr(settings, 'AWS_SES_REGION', 'us-east-1')
            )
            
            # Prepare email
            from_email_addr = from_email or provider.from_email
            from_name_str = from_name or provider.from_name or ""
            
            # Format sender with name if provided
            if from_name_str:
                sender = f'"{from_name_str}" <{from_email_addr}>'
            else:
                sender = from_email_addr
            
            destination = {'ToAddresses': to_emails}
            
            if cc_emails:
                destination['CcAddresses'] = cc_emails
            if bcc_emails:
                destination['BccAddresses'] = bcc_emails
            
            message = {
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {}
            }
            
            if text_content:
                message['Body']['Text'] = {'Data': text_content, 'Charset': 'UTF-8'}
            
            if html_content:
                message['Body']['Html'] = {'Data': html_content, 'Charset': 'UTF-8'}
            
            # Send email
            response = ses_client.send_email(
                Source=sender,
                Destination=destination,
                Message=message,
                ReplyToAddresses=[reply_to] if reply_to else [provider.reply_to] if provider.reply_to else []
            )
            
            message_id = response['MessageId']
            logger.info(f"AWS SES: Email sent successfully via '{provider.name}'. MessageId: {message_id}")
            
            return {
                'success': True,
                'message_id': message_id
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS SES ClientError: {error_code} - {error_message}")
            
            # Handle specific AWS SES errors
            if error_code == 'MessageRejected':
                helpful_error = f"""
AWS SES Error: Email was rejected by Amazon SES.
Reason: {error_message}

Common causes:
1. The sender email '{from_email or provider.from_email}' is not verified in AWS SES
2. Your AWS SES account is in sandbox mode (can only send to verified emails)
3. The recipient email is invalid or blocked

To fix:
1. Verify the sender email in AWS SES Console
2. Request production access to send to any email
3. Check recipient email validity

Provider: {provider.name}
                """.strip()
                return {
                    'success': False,
                    'error': helpful_error,
                    'error_type': 'message_rejected',
                    'error_code': error_code
                }
            
            return {
                'success': False,
                'error': f"AWS SES Error ({error_code}): {error_message}",
                'error_code': error_code
            }
        except Exception as e:
            logger.error(f"AWS SES error: {str(e)}")
            return {
                'success': False,
                'error': f"AWS SES Error: {str(e)}"
            }
    
    def _send_via_smtp(self, provider: EmailProviderConfig, to_emails: List[str],
                      subject: str, html_content: str, text_content: str,
                      from_email: str, from_name: str, reply_to: str,
                      cc_emails: List[str], bcc_emails: List[str],
                      attachments: List[Tuple[str, str, str]]) -> Dict[str, Any]:
        """Send email via SMTP"""
        try:
            from_email_addr = from_email or provider.from_email
            from_name_str = from_name or provider.from_name or ""
            
            # Create email message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content or html_content,
                from_email=f"{from_name_str} <{from_email_addr}>" if from_name_str else from_email_addr,
                to=to_emails,
                cc=cc_emails or [],
                bcc=bcc_emails or []
            )
            
            if html_content:
                msg.attach_alternative(html_content, "text/html")
            
            if reply_to:
                msg.reply_to = [reply_to]
            elif provider.reply_to:
                msg.reply_to = [provider.reply_to]
            
            # Add attachments
            if attachments:
                for filename, content, mimetype in attachments:
                    msg.attach(filename, content, mimetype)
            
            # Configure SMTP settings
            smtp_settings = {
                'host': provider.smtp_host,
                'port': provider.smtp_port,
                'username': provider.smtp_username,
                'password': self._decrypt_credential(provider.smtp_password),
                'use_tls': provider.smtp_use_tls,
                'use_ssl': provider.smtp_use_ssl,
            }
            
            # Send email
            msg.send()
            
            return {
                'success': True,
                'message_id': f"smtp_{int(time.time())}"
            }
            
        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _log_usage(self, provider: EmailProviderConfig, emails_sent: int, 
                   success: bool, response_time: float):
        """Log email usage for a provider"""
        try:
            EmailProviderUsageLog.objects.create(
                provider=provider,
                emails_sent=emails_sent,
                success_count=emails_sent if success else 0,
                failure_count=emails_sent if not success else 0,
                total_response_time=response_time * emails_sent
            )
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")
    
    def test_provider(self, provider: EmailProviderConfig, test_email: str) -> Dict[str, Any]:
        """Test email provider configuration"""
        try:
            result = self.send_email(
                to_emails=[test_email],
                subject="Test Email from Insurance System",
                html_content="<p>This is a test email to verify email provider configuration.</p>",
                text_content="This is a test email to verify email provider configuration.",
                from_email=provider.from_email,
                from_name=provider.from_name
            )
            
            # Update health status
            provider.update_health_status(result['success'], result.get('error'))
            
            return result
            
        except Exception as e:
            logger.error(f"Provider test failed: {str(e)}")
            provider.update_health_status(False, str(e))
            return {
                'success': False,
                'error': str(e),
                'provider_name': provider.name
            }
    
    def check_provider_health(self, provider: EmailProviderConfig) -> bool:
        """Check if a provider is healthy"""
        try:
            if provider.provider_type == 'sendgrid':
                return self._check_sendgrid_health(provider)
            elif provider.provider_type == 'aws_ses':
                return self._check_aws_ses_health(provider)
            elif provider.provider_type == 'smtp':
                return self._check_smtp_health(provider)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Health check failed for {provider.name}: {str(e)}")
            provider.update_health_status(False, str(e))
            return False
    
    def _check_sendgrid_health(self, provider: EmailProviderConfig) -> bool:
        """Check SendGrid health"""
        try:
            api_key = self._decrypt_credential(provider.api_key)
            if not api_key:
                return False
            
            # Test API key validity
            sg = SendGridAPIClient(api_key=api_key)
            response = sg.client.user.get()
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"SendGrid health check failed: {str(e)}")
            return False
    
    def _check_aws_ses_health(self, provider: EmailProviderConfig) -> bool:
        """Check AWS SES health"""
        try:
            access_key = self._decrypt_credential(provider.access_key_id)
            secret_key = self._decrypt_credential(provider.secret_access_key)
            
            if not access_key or not secret_key:
                logger.warning(f"AWS SES health check failed for {provider.name}: Missing credentials")
                return False
            
            # Test credentials
            ses_client = boto3.client(
                'ses',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=provider.aws_region or getattr(settings, 'AWS_SES_REGION', 'us-east-1')
            )
            
            # Get sending quota
            response = ses_client.get_send_quota()
            
            if 'Max24HourSend' in response:
                logger.info(f"AWS SES health check passed for {provider.name}. Quota: {response['Max24HourSend']}")
                provider.update_health_status(True)
                return True
            
            return False
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"AWS SES health check failed for {provider.name}: {error_code} - {str(e)}")
            provider.update_health_status(False, str(e))
            return False
        except Exception as e:
            logger.error(f"AWS SES health check failed for {provider.name}: {str(e)}")
            provider.update_health_status(False, str(e))
            return False
    
    def _check_smtp_health(self, provider: EmailProviderConfig) -> bool:
        """Check SMTP health"""
        try:
            import smtplib
            
            if not provider.smtp_host or not provider.smtp_port:
                return False
            
            # Test SMTP connection
            if provider.smtp_use_ssl:
                server = smtplib.SMTP_SSL(provider.smtp_host, provider.smtp_port)
            else:
                server = smtplib.SMTP(provider.smtp_host, provider.smtp_port)
                if provider.smtp_use_tls:
                    server.starttls()
            
            if provider.smtp_username and provider.smtp_password:
                password = self._decrypt_credential(provider.smtp_password)
                server.login(provider.smtp_username, password)
            
            server.quit()
            return True
            
        except Exception as e:
            logger.error(f"SMTP health check failed: {str(e)}")
            return False
