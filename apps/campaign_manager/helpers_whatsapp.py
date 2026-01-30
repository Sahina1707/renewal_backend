from twilio.rest import Client
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

try:
    TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
    TWILIO_FROM_NUMBER = settings.TWILIO_PHONE_NUMBER 
    
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.error("Twilio credentials (SID or TOKEN) are missing in settings.")
        client = None
    else:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

except Exception as e:
    logger.error(f"Failed to initialize Twilio client: {e}")
    client = None


def send_whatsapp_message(contact_phone, template_provider_id, custom_params=None):
    if not client:
        return False, "Twilio client not initialized. Check settings.", None

    if not TWILIO_FROM_NUMBER:
        return False, "Twilio 'From' number (TWILIO_PHONE_NUMBER) not set.", None

    content_variables = {}
    if custom_params:
        for i, value in enumerate(custom_params, 1):
            content_variables[str(i)] = str(value)

    contact_phone_clean = str(contact_phone).replace(" ", "").replace("-", "")
    
    if len(contact_phone_clean) == 10 and not contact_phone_clean.startswith('+'):
        contact_phone_e164 = f"+91{contact_phone_clean}"
    elif contact_phone_clean.startswith('+'):
        contact_phone_e164 = contact_phone_clean
    else:
        contact_phone_e164 = f"+{contact_phone_clean}" 

    from_number_prefixed = f"whatsapp:{TWILIO_FROM_NUMBER}"
    to_number_prefixed = f"whatsapp:{contact_phone_e164}"

    try:
        message = client.messages.create(
            content_sid=template_provider_id, 
            
            from_=from_number_prefixed,
            
            content_variables=content_variables if content_variables else None,
            
            to=to_number_prefixed
        )

        message_id = message.sid
        logger.info(f"Twilio message queued to {to_number_prefixed}. Msg SID: {message_id}")
        return True, None, message_id 

    except Exception as e:
        logger.error(f"Twilio API Error for {to_number_prefixed}: {e}", exc_info=True)
        return False, str(e), None