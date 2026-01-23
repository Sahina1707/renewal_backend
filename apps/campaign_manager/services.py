from apps.email_provider.models import EmailProviderConfig
from apps.email_provider.services import EmailProviderService
from apps.sms_provider.services import SmsService, SmsApiException
from apps.campaign_manager.models import CampaignLog, Campaign
from apps.audience_manager.models import AudienceContact
class CampaignService:
    def _log_failure(self, campaign: Campaign, contact: AudienceContact, error_message: str, provider: EmailProviderConfig = None):
        print(f"❌ Log Failure: {error_message}")
        CampaignLog.objects.create(
            campaign=campaign,
            contact=contact,
            status='failed',
            error_message=str(error_message), 
            message_provider_id=provider.id if provider else None
        )

    def _log_success(self, campaign, contact, provider):
        print(f"✅ Log Success: Email sent to {contact.email}")
        CampaignLog.objects.create(
            campaign=campaign,
            contact=contact,
            status='sent',
            message_provider_id=provider.id if provider else None
        )

    def execute_step(self, campaign, step, contact):
        rendered_content = step.template.content.replace("{{name}}", contact.name)
        provider = getattr(campaign, 'email_provider', None)

        if not provider:
            print(f"⚠️ DEBUG: Campaign {campaign.id} has no provider. Fetching Default...")
            
            provider = EmailProviderConfig.objects.filter(is_default=True, is_active=True).first()
            
            if provider:
                print(f"✅ DEBUG: Auto-selected Default: {provider.name}")
                campaign.email_provider = provider
                campaign.save(update_fields=['email_provider'])
            else:
                print("❌ CRITICAL: No default provider found in Database!")
                self._log_failure(campaign, contact, "No Provider Configured")
                return

        try:
            service = EmailProviderService()
            result = service.send_email(
                to_emails=[contact.email],
                subject=step.template.subject,
                html_content=rendered_content,
            )
            
            if result['success']:
                self._log_success(campaign, contact, provider)
            else:
                self._log_failure(campaign, contact, result.get('error'), provider)

        except Exception as e:
            print(f"🔥 CRITICAL EXCEPTION: {str(e)}")
            self._log_failure(campaign, contact, str(e), provider)