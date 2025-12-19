import logging
import time
from typing import Dict, Any, Type, Optional

import requests
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from django.conf import settings
from cryptography.fernet import Fernet

from .models import CallProviderConfig, CallProviderUsageLog

logger = logging.getLogger(__name__)


# ============================================================
#  EXCEPTION
# ============================================================

class CallApiException(Exception):
    """Custom exception for CALL API errors."""
    pass


# ============================================================
#  BASE CLASS
# ============================================================

class BaseCallService:
    """
    Abstract base class for all CALL provider services.
    Uses CallProviderConfig instead of SmsProvider.
    """

    def __init__(self, provider_model: CallProviderConfig):
        self.provider = provider_model
        # Encryption key (same idea as WhatsApp service)
        self.encryption_key = getattr(settings, "CALL_ENCRYPTION_KEY", None)

        # Build a credentials dict (secrets decrypted here)
        self.credentials = {
            # Twilio
            "twilio_account_sid": provider_model.twilio_account_sid,
            "twilio_auth_token": self._decrypt(provider_model.twilio_auth_token),
            "twilio_from_number": provider_model.twilio_from_number,
            "twilio_status_callback_url": provider_model.twilio_status_callback_url,
            "twilio_voice_url": provider_model.twilio_voice_url,

            # Exotel
            "exotel_api_key": self._decrypt(provider_model.exotel_api_key),
            "exotel_api_token": self._decrypt(provider_model.exotel_api_token),
            "exotel_account_sid": provider_model.exotel_account_sid,
            "exotel_subdomain": provider_model.exotel_subdomain,  # e.g. api.exotel.com
            "exotel_caller_id": provider_model.exotel_caller_id,

            # Ubona
            "ubona_api_key": self._decrypt(provider_model.ubona_api_key),
            "ubona_api_url": provider_model.ubona_api_url,        # base or health URL
            "ubona_account_sid": provider_model.ubona_account_sid,
            "ubona_caller_id": provider_model.ubona_caller_id,
        }

    # ---------- encryption helpers (decrypt only here) ----------

    def _decrypt(self, value: str) -> str:
        """
        Decrypt a credential using CALL_ENCRYPTION_KEY.
        If decryption fails or key is missing, returns original value.
        """
        if not self.encryption_key or not value:
            return value
        try:
            fernet = Fernet(self.encryption_key.encode())
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            # If value is already plain or key changed, fall back
            return value

    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        """Place an outbound call (to be implemented per provider)."""
        raise NotImplementedError("This method must be implemented by a subclass.")

    def health_check(self) -> Dict[str, Any]:
        """
        Must be implemented in subclasses.

        healthy:
            {'status': 'connected', 'details': 'Credentials valid'}

        unhealthy (missing/invalid credentials, API failure):
            {'status': 'unhealthy', 'error': 'Some error message'}
        """
        raise NotImplementedError("This method must be implemented by a subclass.")


# ============================================================
#  TWILIO CALL SERVICE
# ============================================================

class TwilioCallService(BaseCallService):
    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        """
        NOTE:
        Currently not used – your module is only logging, not placing calls.
        If in future you want to actually dial calls from here,
        implement Twilio client.calls.create(...) in this method.
        """
        raise CallApiException("Twilio call not implemented yet.")

    def health_check(self) -> Dict[str, Any]:
        """
        Health check rules:
        - Missing credentials           => status = 'unhealthy'
        - Invalid credentials (401/403) => status = 'unhealthy'
        - Other Twilio/API errors       => status = 'unhealthy'
        - Valid credentials + API OK    => status = 'connected'
        """
        account_sid = self.credentials.get('twilio_account_sid')
        auth_token = self.credentials.get('twilio_auth_token')

        # Missing configuration => unhealthy
        if not account_sid or not auth_token:
            return {
                'status': 'unhealthy',
                'error': "Twilio credentials (Account SID or Auth Token) are not configured.",
            }

        try:
            client = Client(account_sid, auth_token)
            # This will fail if SID/token are invalid
            client.api.v2010.accounts(account_sid).fetch()

            return {
                'status': 'connected',
                'details': 'Credentials valid',
            }

        except TwilioRestException as e:
            logger.error(f"Twilio API Error (Call health check): {e}")

            status_code = getattr(e, 'status', None)
            if status_code in (401, 403):
                msg = 'Invalid Twilio Account SID or Auth Token.'
            else:
                msg = str(e)

            return {
                'status': 'unhealthy',
                'error': msg,
            }

        except Exception as e:
            logger.error(f"Twilio Call health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
            }


# ============================================================
#  EXOTEL CALL SERVICE (with real API validation)
# ============================================================

class ExotelCallService(BaseCallService):
    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        """
        TODO: implement real Exotel call if needed.
        """
        raise CallApiException("Exotel call not implemented yet.")

    def _build_exotel_account_url(self, subdomain: str, account_sid: str) -> str:
        """
        Build a safe "account details" URL to validate credentials.

        We use a simple GET on the account details as a health check:
        - 200 OK   => credentials valid
        - 401/403  => invalid credentials
        """
        # If subdomain already contains scheme (http/https)
        if subdomain and subdomain.startswith("http"):
            base = subdomain.rstrip("/")
        else:
            # Fallback: build with https://<subdomain>
            # Typical values: api.exotel.com / api.in.exotel.com
            base = f"https://{subdomain or 'api.exotel.com'}"

        # Exotel v1 base pattern: https://api.exotel.com/v1/Accounts/<sid>.json
        return f"{base}/v1/Accounts/{account_sid}.json"

    def health_check(self) -> Dict[str, Any]:
        """
        Health check for Exotel (real API validation):

        - Missing mandatory fields          => status 'unhealthy'
        - GET on account details endpoint:
            - 200 OK                        => status 'connected'
            - 401/403 (unauthorized/forbid) => status 'unhealthy' (invalid creds)
            - Any other error               => status 'unhealthy'
        """
        try:
            api_key = self.credentials.get('exotel_api_key')
            api_token = self.credentials.get('exotel_api_token')
            account_sid = self.credentials.get('exotel_account_sid')
            subdomain = self.credentials.get('exotel_subdomain')
            caller_id = self.credentials.get('exotel_caller_id')

            missing = []
            if not api_key:
                missing.append("API Key")
            if not api_token:
                missing.append("API Token")
            if not account_sid:
                missing.append("Account SID")
            if not subdomain:
                missing.append("Subdomain")
            if not caller_id:
                missing.append("Caller ID")

            # Missing config => unhealthy
            if missing:
                return {
                    'status': 'unhealthy',
                    'error': "Missing Exotel fields: " + ", ".join(missing),
                }

            url = self._build_exotel_account_url(subdomain=subdomain, account_sid=account_sid)

            try:
                resp = requests.get(url, auth=(api_key, api_token), timeout=10)
            except requests.RequestException as e:
                logger.error(f"Exotel API request failed: {e}")
                return {
                    'status': 'unhealthy',
                    'error': f"Failed to reach Exotel API: {e}",
                }

            # Handle HTTP status codes
            if resp.status_code == 200:
                return {
                    'status': 'connected',
                    'details': 'Exotel credentials valid',
                }
            elif resp.status_code in (401, 403):
                # Unauthorized / Forbidden => invalid credentials or account access
                return {
                    'status': 'unhealthy',
                    'error': f"Invalid Exotel credentials or access forbidden (HTTP {resp.status_code}).",
                }
            else:
                # Other errors -> unhealthy with response info
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text

                logger.error(f"Exotel health check HTTP {resp.status_code}: {body}")
                return {
                    'status': 'unhealthy',
                    'error': f"Exotel health check failed with HTTP {resp.status_code}: {body}",
                }

        except Exception as e:
            logger.error(f"Exotel Call health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
            }


# ============================================================
#  UBONA CALL SERVICE (with generic API validation)
# ============================================================

class UbonaCallService(BaseCallService):
    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        """
        TODO: implement real Ubona call if needed.
        """
        raise CallApiException("Ubona call not implemented yet.")

    def health_check(self) -> Dict[str, Any]:
        """
        Health check for Ubona:

        - Missing mandatory fields      => status 'unhealthy'
        - Calls configured ubona_api_url as health/validation endpoint:
            - 200 OK                    => status 'connected'
            - 401/403                   => status 'unhealthy' (invalid key / auth)
            - Any other error           => status 'unhealthy'
        """
        try:
            api_key = self.credentials.get('ubona_api_key')
            api_url = self.credentials.get('ubona_api_url')
            account_sid = self.credentials.get('ubona_account_sid')
            caller_id = self.credentials.get('ubona_caller_id')

            missing = []
            if not api_key:
                missing.append("API Key")
            if not api_url:
                missing.append("API URL")
            if not account_sid:
                missing.append("Account SID")
            if not caller_id:
                missing.append("Caller ID")

            if missing:
                return {
                    'status': 'unhealthy',
                    'error': "Missing Ubona fields: " + ", ".join(missing),
                }

            health_url = api_url.strip()

            headers = {
                "X-API-KEY": api_key,
            }

            try:
                resp = requests.get(health_url, headers=headers, timeout=10)
            except requests.RequestException as e:
                logger.error(f"Ubona API health request failed: {e}")
                return {
                    'status': 'unhealthy',
                    'error': f"Failed to reach Ubona API: {e}",
                }

            if resp.status_code == 200:
                return {
                    'status': 'connected',
                    'details': 'Ubona credentials valid (health endpoint returned 200)',
                }
            elif resp.status_code in (401, 403):
                return {
                    'status': 'unhealthy',
                    'error': f"Invalid Ubona credentials or access forbidden (HTTP {resp.status_code}).",
                }
            else:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text

                logger.error(f"Ubona health check HTTP {resp.status_code}: {body}")
                return {
                    'status': 'unhealthy',
                    'error': f"Ubona health check failed with HTTP {resp.status_code}: {body}",
                }

        except Exception as e:
            logger.error(f"Ubona Call health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
            }


# ============================================================
#  FACTORY + PUBLIC SERVICE (CallProviderService)
# ============================================================

class CallProviderService:
    """
    Factory + helper for CALL providers.
    """

    PROVIDER_MAP: Dict[str, Type[BaseCallService]] = {
        'twilio': TwilioCallService,
        'exotel': ExotelCallService,
        'ubona': UbonaCallService,
    }

    def __init__(self):
        self.encryption_key = getattr(settings, "CALL_ENCRYPTION_KEY", None)

    # ---------- encryption for serializers ----------

    def _encrypt_credential(self, value: str) -> str:
        """
        Encrypt a credential using CALL_ENCRYPTION_KEY.
        If encryption fails or key missing, returns original value.
        """
        if not self.encryption_key or not value:
            return value
        try:
            fernet = Fernet(self.encryption_key.encode())
            return fernet.encrypt(value.encode()).decode()
        except Exception:
            return value

    # ---------- factory helpers ----------

    def _get_provider_class(self, provider_type: str) -> Optional[Type[BaseCallService]]:
        """Returns the correct service class based on the provider type."""
        return self.PROVIDER_MAP.get(provider_type)

    def get_service_instance(self, provider_id: int = None) -> BaseCallService:
        """
        Gets an instance of the correct provider service.
        If provider_id is None, fetch the 'default' provider.
        """
        try:
            if provider_id:
                provider_model = CallProviderConfig.objects.get(
                    id=provider_id,
                    is_active=True,
                    is_deleted=False,
                )
            else:
                logger.info("No call provider ID given, fetching default CALL provider.")
                provider_model = CallProviderConfig.objects.get(
                    is_default=True,
                    is_active=True,
                    is_deleted=False,
                )
        except CallProviderConfig.DoesNotExist:
            logger.error(f"No active CALL provider found for ID: {provider_id} or as default.")
            raise CallApiException("No active or default CALL provider configured.")
        except CallProviderConfig.MultipleObjectsReturned:
            logger.error("Multiple default CALL providers found. Please set only one default.")
            raise CallApiException("Multiple default CALL providers found.")

        ProviderClass = self._get_provider_class(provider_model.provider_type)

        if not ProviderClass:
            logger.error(f"No service class found for CALL provider type: {provider_model.provider_type}")
            raise CallApiException(f"Provider type {provider_model.provider_type} is not supported.")

        return ProviderClass(provider_model)

    # --------------------------------------------------------
    #  TEST PROVIDER (play button)
    # --------------------------------------------------------
    def test_provider(self, provider: CallProviderConfig, test_number: str) -> Dict[str, Any]:
        """
        Called when you click the play button.
        For now: just simulate a call.
        """
        start = time.time()
        time.sleep(0.2)  # simulate network delay
        elapsed = round(time.time() - start, 3)

        return {
            'success': True,
            'message': f"Test call simulated for {test_number} using {provider.name}",
            'response_time': elapsed,
        }

    # --------------------------------------------------------
    #  HEALTH CHECK (used by /health_check and /health_status)
    # --------------------------------------------------------
    def check_provider_health(self, provider: CallProviderConfig, user=None) -> Dict[str, Any]:
        """
        Build correct service, call health_check(), update provider status,
        create health log, and return a summary dict.
        """
        start = time.time()

        try:
            service = self.get_service_instance(provider_id=provider.id)
        except CallApiException as e:
            logger.error(str(e))
            return {
                'success': False,
                'status': 'unhealthy',
                'details': str(e),
                'response_time': 0.0,
            }

        result = service.health_check()
        status_val = result.get('status', 'unhealthy')
        details = result.get('details') or result.get('error') or ''
        success = status_val == 'connected'
        response_time = round(time.time() - start, 3)

        try:
            provider.update_status(
                is_healthy=success,
                error_message=None if success else details,
                response_time=response_time,
                test_type="health_check",
                user=user,
            )
        except Exception as e:
            logger.error(f"Failed to update call provider status for {provider.name}: {e}")

        return {
            'success': success,
            'status': status_val,
            'details': details,
            'response_time': response_time,
        }

    # --------------------------------------------------------
    #  GENERIC USAGE LOG HELPER (ALL PROVIDERS)
    # --------------------------------------------------------
    @staticmethod
    def log_usage_for_provider(
        provider: CallProviderConfig,
        *,
        status: str,
        success: bool,
        duration: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create a CallProviderUsageLog + increment provider counters.

        Works for Twilio, Exotel, Ubona – any provider. Call this from
        webhooks or other code whenever a call finishes.
        """
        data: Dict[str, Any] = extra.copy() if extra else {}
        data.setdefault("status", status)

        CallProviderUsageLog.objects.create(
            provider=provider,
            calls_made=1,
            success_count=1 if success else 0,
            failure_count=0 if success else 1,
            total_response_time=duration or 0.0,
            data=data,
        )

        provider.increment_usage(count=1)
