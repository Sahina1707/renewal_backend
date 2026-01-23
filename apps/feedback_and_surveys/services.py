from django.conf import settings
from .models import SurveySubmission
from apps.audience_manager.models import AudienceContact
from django.core.mail import send_mail
from apps.email_provider.services import EmailProviderService

class DistributionService:
    """
    Handles the logic of sending surveys via different channels.
    Integrates with your Email/SMS/WhatsApp providers.
    """

    def __init__(self, survey):
        self.survey = survey
        self.audience = survey.audience

    def launch_campaign(self, channels=['email']):
        """
        Main entry point. Loops through the audience and sends via selected channels.
        """
        if not self.audience:
            return {"error": "No audience assigned to this survey."}

        contacts = self.audience.contacts.filter(is_deleted=False)
        sent_count = 0

        for contact in contacts:
            # 1. Generate Unique Link (So we know WHO filled it out)
            # We append ?c=CONTACT_ID to the public URL
            unique_link = f"{settings.SITE_URL}/feedback/public/{self.survey.id}/?c={contact.id}"
            
            # 2. Send based on selected channels
            if 'email' in channels and contact.email:
                self._send_email(contact, unique_link)
                sent_count += 1
            
            if 'sms' in channels and contact.phone:
                self._send_sms(contact, unique_link)
                sent_count += 1
                
            if 'whatsapp' in channels and contact.phone:
                self._send_whatsapp(contact, unique_link)
                sent_count += 1

        return {"status": "success", "sent_count": sent_count}

    # --- PROVIDER INTEGRATIONS (Fill these with your actual provider code) ---

    def _send_email(self, contact, link):
        subject = f"We'd love your feedback, {contact.name}!"
        message = f"""
        Hi {contact.name},
        Thank you for being a valued customer. We would love to hear your through your feedback.Please click the link below to answer a quick survey:
        {link}
        Best Regards,
        The Renewal- Team
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL, # e.g., 'noreply@yourcompany.com'
                [contact.email],
                fail_silently=False,
            )
            print(f"✅ [Email Sent] To: {contact.email}")
        except Exception as e:
            print(f"❌ [Email Failed] {e}")
    def _send_sms(self, contact, link):
        body = f"Hi {contact.name}, rate us here: {link}"
        
        # EXAMPLE: Calling Twilio or similar
        # sms_provider.send(to=contact.phone, body=body)
        print(f"[SMS Sent] To: {contact.phone} | Link: {link}")

    def _send_whatsapp(self, contact, link):
        # WhatsApp usually requires templates
        print(f"[WhatsApp Sent] To: {contact.phone} | Link: {link}")

    def send_transactional(self, customer, channels=['email']):
        
        unique_link = f"{settings.BASE_URL}/feedback/public/{self.survey.id}/?c={contact.id}"        
        print(f"--- [Automation] Triggering Survey for {customer.name} ---")

        if 'email' in channels and customer.email:
            self._send_email_transactional(customer, unique_link)
        
        if 'sms' in channels and customer.phone:
            self._send_sms_transactional(customer, unique_link)

    def _send_email_transactional(self, customer, link):
        print(f"🚀 [Email Sent] To: {customer.email} | Subject: How was your experience? | Link: {link}")

    def _send_sms_transactional(self, customer, link):
        print(f"🚀 [SMS Sent] To: {customer.phone} | Msg: Rate us here: {link}")