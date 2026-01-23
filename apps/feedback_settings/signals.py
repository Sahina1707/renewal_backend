import requests # Make sure to install: pip install requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.feedback_and_surveys.models import SurveySubmission
from apps.feedback_settings.models import SurveySettings, IntegrationCredential
from apps.email_provider.services import EmailProviderService 

@receiver(post_save, sender=SurveySubmission)
def survey_notification_handler(sender, instance, created, **kwargs):
    if not created:
        return

    # 1. Get Settings & Owner
    owner = instance.survey.owner
    try:
        settings = SurveySettings.objects.get(owner=owner)
    except SurveySettings.DoesNotExist:
        return 

    # --- EMAIL LOGIC (Existing) ---
    is_urgent = instance.rating < settings.negative_feedback_threshold
    if settings.email_notifications and is_urgent:
        email_service = EmailProviderService() 
        email_service.send_email(
            to_emails=[owner.email],
            subject=f"Urgent Feedback: {instance.rating} Stars",
            text_content=f"User {instance.customer} is unhappy. Comment: {instance.comment}"
        )

    # --- ZAPIER LOGIC (New) ---
    # Check if the user has activated Zapier
    try:
        zapier_config = IntegrationCredential.objects.get(
            owner=owner, 
            provider='zapier', 
            is_active=True
        )
        
        if zapier_config.webhook_url:
            # Prepare the data packet
            payload = {
                "event": "new_feedback",
                "survey_title": instance.survey.title,
                "customer_name": instance.customer.name if instance.customer else "Anonymous",
                "rating": instance.rating,
                "comment": instance.comment,
                "status": instance.status,
                "submitted_at": str(instance.created_at)
            }
            
            # Send the POST request to Zapier
            try:
                requests.post(zapier_config.webhook_url, json=payload, timeout=5)
                print("Successfully sent data to Zapier")
            except Exception as e:
                print(f"Failed to send to Zapier: {e}")
    except IntegrationCredential.DoesNotExist:
        pass
    try:
        sf_config = IntegrationCredential.objects.get(
            owner=owner, 
            provider='salesforce', 
            is_active=True
        )
        
        # Salesforce typically requires an Instance URL and an Access Token
        # We assume you stored the Instance URL in 'meta_data' and Token in 'api_key'
        instance_url = sf_config.meta_data.get('instance_url') 
        access_token = sf_config.api_key
        
        if instance_url and access_token:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # 1. Create a "Task" or "Note" object in Salesforce linked to a generic Contact
            # (In a real scenario, you'd first search for the Contact ID by email)
            sf_payload = {
                "Subject": f"Survey Response: {instance.survey.title}",
                "Description": f"Rating: {instance.rating}/5\nComment: {instance.comment}",
                "Status": "Completed",
                "Priority": "Normal"
            }
            
            sf_endpoint = f"{instance_url}/services/data/v53.0/sobjects/Task/"
            
            try:
                response = requests.post(sf_endpoint, json=sf_payload, headers=headers)
                if response.status_code == 201:
                    print(f"✅ [Salesforce] Created Task ID: {response.json().get('id')}")
                else:
                    print(f"❌ [Salesforce] Error: {response.text}")
            except Exception as e:
                print(f"❌ [Salesforce] Connection Failed: {e}")
    except IntegrationCredential.DoesNotExist:
        pass
    try:
        slack_config = IntegrationCredential.objects.get(
            owner=owner, 
            provider='slack', 
            is_active=True
        )
        if slack_config.webhook_url:
            slack_msg = {
                "text": f"🔔 New Feedback: {instance.rating}/5 stars from {instance.customer or 'Anonymous'}\nReview: {instance.comment}"
            }
            requests.post(slack_config.webhook_url, json=slack_msg)
    except IntegrationCredential.DoesNotExist:
        pass