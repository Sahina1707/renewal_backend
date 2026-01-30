import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template import Template, Context
from .models import Campaign, CampaignRecipient
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.email_provider.services import EmailProviderService

logger = logging.getLogger(__name__)
class EmailCampaignService:
    @staticmethod
    def send_campaign_emails(campaign_id):
        try:
            import traceback

            logger.info(f"Starting email sending for campaign {campaign_id}")

            campaign = Campaign.objects.get(id=campaign_id)
            logger.info(f"Found campaign: {campaign.name}")

            if 'email' not in campaign.channels:
                logger.warning(f"Campaign {campaign_id} does not include email channel")
                return {"error": "Campaign does not include email channel"}

            recipients = CampaignRecipient.objects.filter(
                campaign=campaign,
                email_status='pending'
            ).select_related('customer', 'policy')

            logger.info(f"Found {recipients.count()} pending recipients")

            if not recipients.exists():
                logger.warning(f"No pending recipients found for campaign {campaign_id}")
                return {"message": "No pending recipients found for this campaign"}

            sent_count = 0
            failed_count = 0

            for recipient in recipients:
                try:
                    logger.info(f"Processing recipient {recipient.pk}: {recipient.customer.email}")
                    success = EmailCampaignService._send_individual_email(recipient)

                    if success:
                        sent_count += 1
                        logger.info(f"Email sent successfully to {recipient.customer.email}")
                    else:
                        recipient.email_status = 'failed'
                        recipient.save()
                        failed_count += 1
                        logger.error(f"Email failed to {recipient.customer.email}")

                except Exception as e:
                    logger.error(f"Error sending email to recipient {recipient.pk}: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    recipient.email_status = 'failed'
                    recipient.save()
                    failed_count += 1

            campaign.update_campaign_statistics()

            if sent_count > 0:
                campaign.status = 'completed' if failed_count == 0 else 'running'

            campaign.save()

            logger.info(f"Campaign {campaign_id} email sending completed: {sent_count} sent, {failed_count} failed")

            return {
                "success": True,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "message": f"Sent {sent_count} emails successfully, {failed_count} failed"
            }

        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return {"error": "Campaign not found"}
        except Exception as e:
            logger.error(f"Error sending campaign emails: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}
    
    @staticmethod
    def _send_individual_email(recipient):
        try:
            import traceback

            customer = recipient.customer
            campaign = recipient.campaign

            logger.info(f"Starting email send to {customer.email} for campaign {campaign.id}")

            recipient.email_status = 'queued'
            recipient.save()

            template_content = campaign.template.content if campaign.template else "Default email content"
            subject = campaign.template.subject if campaign.template else campaign.name

            email_content = EmailCampaignService._process_template(
                template_content,
                customer,
                recipient.policy,
                campaign,
                recipient
            )

            tracked_content = EmailCampaignService._add_email_tracking(email_content, recipient, campaign)

            import re
            plain_text = re.sub(r'<[^>]+>', '', tracked_content)
            plain_text = plain_text.replace('&nbsp;', ' ').strip()

            recipient.email_content = {
                'html': tracked_content,
                'plain': plain_text,
                'subject': subject
            }

            logger.info(f"Attempting to send email to {customer.email} using SendGrid")

            email_service = EmailProviderService()
            
            provider = getattr(campaign, 'email_provider', None)
            
            if not provider:
                from apps.email_provider.models import EmailProviderConfig
                provider = EmailProviderConfig.objects.filter(is_default=True, is_active=True).first()
            
            if not provider:
                logger.error("❌ CRITICAL: No Email Provider found. Cannot send.")
                recipient.email_status = 'failed'
                recipient.email_error_message = "No active default email provider configured."
                recipient.save()
                return False

            if provider and provider.provider_type == 'sendgrid':
                custom_args = {
                    'campaign_id': str(campaign.id),
                    'recipient_id': str(recipient.id),
                    'tracking_id': str(recipient.tracking_id)
                }
                
                result = email_service.send_email(
                    to_emails=[customer.email],
                    subject=subject,
                    html_content=tracked_content,
                    text_content=plain_text,
                    from_email=str(provider.from_email),
                    from_name=str(provider.from_name) if provider.from_name else None,
                    reply_to=str(provider.reply_to) if provider.reply_to else None,
                    custom_args=custom_args
                )
                
                if result['success']:
                    logger.info(f"SendGrid email sent successfully to {customer.email}")
                    current_time = timezone.now()
                    recipient.email_status = 'sent'  
                    recipient.email_sent_at = current_time
                    recipient.provider_message_id = result.get('message_id')
                    recipient.save()
                    
                    campaign.update_campaign_statistics()
                    
                    return True
                else:
                    error_msg = result.get('error', 'Unknown SendGrid error')
                    logger.error(f"SendGrid email failed to {customer.email}: {error_msg}")
                    raise Exception(f"SendGrid error: {error_msg}")
            else:
                logger.warning("No SendGrid provider available, using Django email fallback")
                return EmailCampaignService._send_individual_email_django_fallback(recipient, tracked_content, plain_text, subject)

        except Exception as e:
            logger.error(f"Error sending individual email: {str(e)}")
            recipient.email_status = 'failed'
            recipient.email_error_message = str(e)
            recipient.save()
            return False
    
    @staticmethod
    def _send_individual_email_django_fallback(recipient, tracked_content, plain_text, subject):
        try:
            from django.core.mail import EmailMultiAlternatives
            import traceback

            customer = recipient.customer
            campaign = recipient.campaign

            logger.info(f"Using Django email fallback for {customer.email}")

            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_text,  
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[customer.email]
            )

            msg.attach_alternative(tracked_content, "text/html")

            try:
                msg.send(fail_silently=False)
                logger.info(f"Django email sent successfully to {customer.email}")
            except Exception as send_error:
                logger.error(f"Django email send failed to {customer.email}: {str(send_error)}")
                raise send_error

            current_time = timezone.now()
            recipient.email_status = 'delivered'  
            recipient.email_sent_at = current_time
            recipient.email_delivered_at = current_time  
            recipient.save()

            campaign.update_campaign_statistics()

            return True

        except Exception as e:
            logger.error(f"Error in Django email fallback: {str(e)}")
            recipient.email_status = 'failed'
            recipient.email_error_message = str(e)
            recipient.save()
            return False
    
    @staticmethod
    def _process_template(template_content, customer, policy, campaign, recipient=None):
        try:
            from django.template import Template, Context

            context_data = {
                'customer_name': f"{customer.first_name} {customer.last_name}",
                'customer_email': customer.email,
                'customer_phone': customer.phone,
                'company_name': 'Your Insurance Company',
                'campaign_name': campaign.name,
                'email': customer.email,
                'phone': customer.phone,
            }

            context_data.update({
                'address': getattr(customer, 'address', ''),
                'city': getattr(customer, 'city', ''),
                'state': getattr(customer, 'state', ''),
                'postal_code': getattr(customer, 'postal_code', ''),
            })

            if policy:
                context_data.update({
                    'policy_number': policy.policy_number,
                    'policy_type': policy.policy_type.name if policy.policy_type else 'N/A',
                    'expiry_date': policy.end_date.strftime('%Y-%m-%d') if policy.end_date else 'N/A',
                    'start_date': policy.start_date.strftime('%Y-%m-%d') if policy.start_date else 'N/A',
                    'premium_amount': str(policy.premium_amount) if hasattr(policy, 'premium_amount') else 'N/A',
                    'policy_status': policy.status if hasattr(policy, 'status') else 'Active',
                    'renewal_link': f"http://localhost:8000/renew/{policy.policy_number}/"
                })

            template = Template(template_content)
            context = Context(context_data)
            processed_content = template.render(context)

            return processed_content

        except Exception as e:
            logger.error(f"Error processing template: {str(e)}")
            return template_content

    @staticmethod
    def _add_email_tracking(email_content, recipient, campaign):
        try:
            if not recipient.tracking_id:
                recipient.save()

            if not ('<html>' in email_content.lower() or '<body>' in email_content.lower()):
                html_content = email_content.replace('\n', '<br>\n')
                email_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    {html_content}
</body>
</html>'''
            
            return email_content

        except Exception as e:
            logger.error(f"Error preparing email content: {str(e)}")
            return email_content