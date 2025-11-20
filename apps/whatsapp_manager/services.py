from twilio.rest import Client
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_agent_message(to_number, message_content):
    """
    Sends a Free Text message (Agent Reply) via Twilio.
    """
    # 1. Load Credentials
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        from_number = settings.TWILIO_PHONE_NUMBER
    except AttributeError:
        logger.error("Twilio settings not found in settings.py")
        return False

    # 2. Format Phone Number (Remove spaces, ensure E.164 format)
    clean_phone = str(to_number).replace(" ", "").replace("-", "")
    if len(clean_phone) == 10 and not clean_phone.startswith('+'):
        clean_phone = f"+91{clean_phone}" # Default to India if 10 digits
    elif not clean_phone.startswith('+'):
        clean_phone = f"+{clean_phone}"

    # 3. Send the Message
    try:
        message = client.messages.create(
            body=message_content,       # <--- Uses 'body' for free text (Agent Chat)
            from_=f"whatsapp:{from_number}",
            to=f"whatsapp:{clean_phone}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp chat reply: {e}")
        return False