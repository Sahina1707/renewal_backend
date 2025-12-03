import requests
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# HEADERS = {
#     "accept": "application/json",
#     "authorization": f"Basic {getattr(settings, 'BUREAU_API_KEY', '')}",
#     "content-type": "application/json"
# }

def bureau_headers():
    return {
        "accept": "application/json",
        "authorization": f"Basic {settings.BUREAU_API_KEY}",
        "content-type": "application/json"
    }


BUREAU_BASE_URL = getattr(settings, 'BUREAU_BASE_URL', 'https://api.sandbox.bureau.id/v2/services')


def verify_email(name, email):
    try:
        url = f"{BUREAU_BASE_URL}/email-name-attributes"
        payload = {
            "consent": True,
            "consentText": "approve Bureau Id to capture and process user data based on internal user consent collected",
            "email": email,
            "name": name,
            "consentType": "explicit"
        }
        
        logger.info(f"Verifying email: {email} for name: {name}")
        response = requests.post(url, headers=bureau_headers(), json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Bureau API response for email verification: {data}")
        
        if data.get("statusCode") == 200:
            name_match_score = data.get("nameEmailMatch", 0)
            if name_match_score >= 70:
                return {"verified": True, "message": "Email verified successfully"}
            else:
                return {"verified": False, "message": "Email name match score too low"}
        else:
            return {"verified": False, "message": "Invalid or unverified email"}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Bureau API request failed for email verification: {str(e)}")
        return {"verified": False, "message": f"Verification service unavailable: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during email verification: {str(e)}")
        return {"verified": False, "message": f"Verification failed: {str(e)}"}


def verify_phone(number):
    try:
        clean_number = number.replace('+', '').strip()
        
        if not clean_number.startswith('91') and len(clean_number) == 10 and clean_number.isdigit():
            clean_number = '91' + clean_number
        
        url = f"{BUREAU_BASE_URL}/number-lookup"
        payload = {
            "consent": True,
            "consentText": "approve Bureau Id to capture and process user data based on internal user consent collected",
            "phoneNumber": clean_number,
            "consentType": "explicit"
        }
        
        logger.info(f"Verifying phone number: {number} (normalized to: {clean_number})")
        response = requests.post(url, headers=bureau_headers(), json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Bureau API response for phone verification: {data}")
        
        if data.get("statusCode") == 200:
            status_name = data.get("statusName", "").upper()
            if status_name in ["DELIVERED_TO_HANDSET", "DELIVERED"]:
                return {"verified": True, "message": "Phone number verified successfully"}
            else:
                return {"verified": False, "message": f"Phone number status: {status_name}"}
        else:
            return {"verified": False, "message": "Invalid or inactive phone number"}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Bureau API request failed for phone verification: {str(e)}")
        return {"verified": False, "message": f"Verification service unavailable: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during phone verification: {str(e)}")
        return {"verified": False, "message": f"Verification failed: {str(e)}"}


def verify_pan(pan):
    try:
        url = f"{BUREAU_BASE_URL}/pan-govt-check"
        payload = {
            "consent": True,
            "consentText": "approve Bureau Id to capture and process user data based on internal user consent collected",
            "pan": pan,
            "consentType": "explicit"
        }
        
        logger.info(f"Verifying PAN: {pan}")
        response = requests.post(url, headers=bureau_headers(), json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Bureau API response for PAN verification: {data}")
        
        if data.get("statusCode") == 200:
            name = data.get("name", "")
            if name:
                return {"verified": True, "message": f"PAN verified successfully. Name: {name}"}
            else:
                return {"verified": False, "message": "PAN verification failed - no name found"}
        else:
            return {"verified": False, "message": "Invalid or unverified PAN number"}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Bureau API request failed for PAN verification: {str(e)}")
        return {"verified": False, "message": f"Verification service unavailable: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during PAN verification: {str(e)}")
        return {"verified": False, "message": f"Verification failed: {str(e)}"}


def log_verification_attempt(customer_id, verification_type, value, result):
    logger.info(
        f"Verification attempt - Customer: {customer_id}, "
        f"Type: {verification_type}, Value: {value}, "
        f"Result: {result['verified']}, Message: {result['message']}"
    )
