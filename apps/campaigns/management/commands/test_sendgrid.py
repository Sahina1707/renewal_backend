from django.core.management.base import BaseCommand
from apps.email_provider.models import EmailProviderConfig
from apps.email_provider.services import EmailProviderService
from apps.campaigns.models import Campaign, CampaignRecipient
from apps.campaigns.services import EmailCampaignService

class Command(BaseCommand):
    help = 'Test SendGrid integration for campaign emails'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-email',
            type=str,
            help='Email address to send test email to',
            default='test@example.com'
        )
        parser.add_argument(
            '--campaign-id',
            type=int,
            help='Campaign ID to test with',
            default=None
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting SendGrid Integration Test'))
        self.stdout.write('=' * 50)
        
        self.test_sendgrid_provider()
        
        self.test_sendgrid_send_email(options['test_email'])
        
        if options['campaign_id']:
            self.test_campaign_email_integration(options['campaign_id'])
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('🎉 SendGrid integration test completed!'))

    def test_sendgrid_provider(self):
        """Test if SendGrid provider is configured"""
        self.stdout.write('\n🔍 Checking SendGrid provider configuration...')
        
        sendgrid_providers = EmailProviderConfig.objects.filter(
            provider_type='sendgrid',
            is_active=True,
            is_deleted=False
        )
        
        if not sendgrid_providers.exists():
            self.stdout.write(self.style.ERROR('❌ No active SendGrid providers found!'))
            self.stdout.write('Please create a SendGrid provider in the admin panel.')
            return None
        
        provider = sendgrid_providers.first()
        self.stdout.write(self.style.SUCCESS(f'✅ Found SendGrid provider: {provider.name}'))
        self.stdout.write(f'   - From Email: {provider.from_email}')
        self.stdout.write(f'   - From Name: {provider.from_name}')
        self.stdout.write(f'   - Priority: {provider.priority}')
        self.stdout.write(f'   - Health Status: {provider.health_status}')
        
        return provider

    def test_sendgrid_send_email(self, test_email):
        """Test sending email via SendGrid"""
        self.stdout.write(f'\n📧 Testing SendGrid email sending to {test_email}...')
        
        email_service = EmailProviderService()
        
        provider = email_service.get_available_provider()
        
        if not provider:
            self.stdout.write(self.style.ERROR('❌ No available email providers found!'))
            return False
        
        if provider.provider_type != 'sendgrid':
            self.stdout.write(self.style.WARNING(f'⚠️  Using {provider.provider_type} provider instead of SendGrid'))
        
        result = email_service.send_email(
            to_emails=[test_email],
            subject="Test Email from Insurance System",
            html_content="<h1>Test Email</h1><p>This is a test email from your insurance system.</p>",
            text_content="Test Email\n\nThis is a test email from your insurance system.",
            from_email=str(provider.from_email),
            from_name=str(provider.from_name) if provider.from_name else None
        )
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS('✅ SendGrid email sent successfully!'))
            self.stdout.write(f'   - Message ID: {result.get("message_id", "N/A")}')
            self.stdout.write(f'   - Response Time: {result.get("response_time", "N/A")}s')
        else:
            self.stdout.write(self.style.ERROR('❌ SendGrid email sending failed!'))
            self.stdout.write(f'   - Error: {result.get("error", "Unknown error")}')
        
        return result['success']

    def test_campaign_email_integration(self, campaign_id):
        """Test campaign email integration with SendGrid"""
        self.stdout.write(f'\n🎯 Testing campaign email integration for campaign {campaign_id}...')
        
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            self.stdout.write(f'✅ Found campaign: {campaign.name}')
            
            recipients = CampaignRecipient.objects.filter(
                campaign=campaign,
                email_status='pending'
            )[:1]
            
            if not recipients.exists():
                self.stdout.write(self.style.WARNING('⚠️  No pending recipients found for this campaign.'))
                return False
            
            recipient = recipients.first()
            self.stdout.write(f'✅ Found recipient: {recipient.customer.email}')
            
            self.stdout.write('📤 Testing email sending to campaign recipient...')
            
            success = EmailCampaignService._send_individual_email(recipient)
            
            if success:
                self.stdout.write(self.style.SUCCESS('✅ Campaign email sent successfully via SendGrid!'))
            else:
                self.stdout.write(self.style.ERROR('❌ Campaign email sending failed!'))
            
            return success
            
        except Campaign.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Campaign with ID {campaign_id} not found!'))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error testing campaign email: {str(e)}'))
            return False
