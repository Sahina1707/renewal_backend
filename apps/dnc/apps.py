from django.apps import AppConfig

class DncManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dnc'

    def ready(self):
        # --- PROTECT EMAILS ---
        try:
            from django.core import mail
            from .utils import is_allowed
            
            original_send = mail.send_mail

            def dnc_protected_send(*args, **kwargs):
                subject = args[0] if args else kwargs.get('subject', '')
                recipient = args[1][0] if len(args) > 1 else kwargs.get('recipient_list', [None])[0]
                
                if is_allowed(recipient, text_context=subject):
                    return original_send(*args, **kwargs)
                print(f"DNC BLOCK: Stopped promotional email to {recipient}")
                return 0 # Pretend it sent, but do nothing

            mail.send_mail = dnc_protected_send
        except:
            pass

        # --- PROTECT CALLS ---
        # Note: This intercepts the standard 'request' or 'provider' libraries 
        # that your Call Provider code likely uses to talk to the API.
        try:
            import requests
            from .utils import is_allowed
            
            original_post = requests.post

            def dnc_protected_post(url, *args, **kwargs):
                # If the URL is your call provider's API (e.g., Twilio/Exotel)
                if any(x in url for x in ['api', 'call', 'sms', 'dial']):
                    # Look for the phone number in the data
                    data = kwargs.get('data') or kwargs.get('json') or {}
                    phone = str(data).split('to')[-1][1:15] # Simple scan for number
                    
                    if not is_allowed(phone):
                        print(f"DNC BLOCK: Stopped call to {phone}")
                        # Return a fake "Success" response so your code doesn't crash
                        class FakeResponse:
                            status_code = 200
                            def json(self): return {"status": "blocked_by_dnc"}
                        return FakeResponse()

                return original_post(url, *args, **kwargs)

            requests.post = dnc_protected_post
        except:
            pass