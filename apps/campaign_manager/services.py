from apps.email_provider.models import EmailProviderConfig
from apps.email_provider.services import EmailProviderService
from apps.sms_provider.services import SmsService, SmsApiException
from apps.campaign_manager.models import CampaignLog, Campaign
from apps.audience_manager.models import AudienceContact


class CampaignService:
    """
    A service class to handle campaign-related logic, such as sending emails.
    """

    def _log_failure(self, campaign: Campaign, contact: AudienceContact, error_message: str, provider: EmailProviderConfig = None):
        # Helper to ensure error_message is saved
        print(f"❌ Log Failure: {error_message}")
        CampaignLog.objects.create(
            campaign=campaign,
            contact=contact,
            status='failed',
            error_message=str(error_message), # Ensure string
            message_provider_id=provider.id if provider else None
        )

    def _log_success(self, campaign, contact, provider):
        """Helper method to log a successful send."""
        print(f"✅ Log Success: Email sent to {contact.email}")
        CampaignLog.objects.create(
            campaign=campaign,
            contact=contact,
            status='sent',
            message_provider_id=provider.id if provider else None
        )

    def execute_step(self, campaign, step, contact):
        """
        Executes a campaign step for a given contact, including sending an email.
        """
        # ... (existing code to get template etc) ...
        # For this example, we assume a simple rendered_content
        rendered_content = step.template.content.replace("{{name}}", contact.name)

        # 1. [FIX] Get Provider (Fail-Safe Logic)
        # Try to find the provider attached to the campaign
        # Note: Use 'email_provider' because that is the field name in your new model
        provider = getattr(campaign, 'email_provider', None)

        # If not found, go get the Default one from Settings
        if not provider:
            print(f"⚠️ DEBUG: Campaign {campaign.id} has no provider. Fetching Default...")
            
            # Find the provider where is_default=True and is_active=True
            provider = EmailProviderConfig.objects.filter(is_default=True, is_active=True).first()
            
            if provider:
                print(f"✅ DEBUG: Auto-selected Default: {provider.name}")
                # Save it so we don't have to look it up again
                campaign.email_provider = provider
                campaign.save(update_fields=['email_provider'])
            else:
                print("❌ CRITICAL: No default provider found in Database!")
                # We cannot send without a provider
                self._log_failure(campaign, contact, "No Provider Configured")
                return

        # 2. [FIX] Send the Email
        try:
            # Call your email service here
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
            # 3. [FIX] Print the real error to console
            print(f"🔥 CRITICAL EXCEPTION: {str(e)}")
            self._log_failure(campaign, contact, str(e), provider)
