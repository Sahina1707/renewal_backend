# apps/bot_calling_provider/services.py

import logging
import time
from typing import Dict, Any, Type, Optional

import requests
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from django.conf import settings
from cryptography.fernet import Fernet

from .models import BotCallingProviderConfig

logger = logging.getLogger(__name__)


# ============================================================
#  EXCEPTION
# ============================================================

class BotCallApiException(Exception):
    """Custom exception for BOT CALLING API errors."""
    pass


# ============================================================
#  BASE CLASS
# ============================================================

class BaseBotCallingService:
    """
    Abstract base class for all BOT-calling provider services.
    Uses BotCallingProviderConfig.
    """

    def __init__(self, provider_model: BotCallingProviderConfig):
        self.provider = provider_model
        # Separate key so we don't mix with normal call providers
        self.encryption_key = getattr(settings, "BOT_CALLING_ENCRYPTION_KEY", None)

        # All possible credentials (decrypted here)
        self.credentials = {
            # ---------- Ubona Bot Calling ----------
            "ubona_api_key": self._decrypt(provider_model.ubona_api_key),
            "ubona_api_url": provider_model.ubona_api_url,
            "ubona_account_sid": provider_model.ubona_account_sid,
            "ubona_caller_id": provider_model.ubona_caller_id,
            "ubona_bot_script": provider_model.ubona_bot_script,

            # ---------- House of Agents ----------
            "hoa_api_key": self._decrypt(provider_model.hoa_api_key),
            "hoa_api_url": provider_model.hoa_api_url,
            "hoa_agent_id": provider_model.hoa_agent_id,
            "hoa_campaign_id": provider_model.hoa_campaign_id,
            "hoa_webhook_url": provider_model.hoa_webhook_url,
            "hoa_bot_script": provider_model.hoa_bot_script,

            # ---------- Gnani.ai Bot ----------
            "gnani_api_key": self._decrypt(provider_model.gnani_api_key),
            "gnani_api_url": provider_model.gnani_api_url,
            "gnani_bot_id": provider_model.gnani_bot_id,
            "gnani_project_id": provider_model.gnani_project_id,
            "gnani_language": provider_model.gnani_language,
            "gnani_voice_gender": provider_model.gnani_voice_gender,

            # ---------- Twilio Voice Bot ----------
            "twilio_account_sid": provider_model.twilio_account_sid,
            "twilio_auth_token": self._decrypt(provider_model.twilio_auth_token),
            "twilio_from_number": provider_model.twilio_from_number,
            "twilio_voice_url": provider_model.twilio_voice_url,
            "twilio_status_callback_url": provider_model.twilio_status_callback_url,
            "twilio_bot_script": provider_model.twilio_bot_script,
        }

    # ---------- encryption helpers (decrypt only here) ----------

    def _decrypt(self, value: str) -> str:
        """
        Decrypt a credential using BOT_CALLING_ENCRYPTION_KEY.
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
        """Place an outbound BOT call (to be implemented per provider)."""
        raise NotImplementedError("This method must be implemented by a subclass.")

    def health_check(self) -> Dict[str, Any]:
        """
        Must be implemented in subclasses.

        ✅ healthy:
            {'status': 'connected', 'details': 'Credentials valid'}

        ❌ unhealthy:
            {'status': 'unhealthy', 'error': 'Some error message'}
        """
        raise NotImplementedError("This method must be implemented by a subclass.")


# ============================================================
#  UBONA BOT CALLING SERVICE
# ============================================================

class UbonaBotCallingService(BaseBotCallingService):
    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        # TODO: implement real Ubona bot call
        raise BotCallApiException("Ubona bot call not implemented yet.")

    def health_check(self) -> Dict[str, Any]:
        """
        Health check for Ubona Bot:

        - Missing mandatory fields      => status 'unhealthy'
        - Calls configured ubona_api_url as health/validation endpoint:
            - 200 OK                    => status 'connected'
            - 401/403                   => 'unhealthy' (invalid key / auth)
            - Any other error           => 'unhealthy'
        """
        try:
            api_key = self.credentials.get("ubona_api_key")
            api_url = self.credentials.get("ubona_api_url")
            account_sid = self.credentials.get("ubona_account_sid")
            caller_id = self.credentials.get("ubona_caller_id")

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
                    "status": "unhealthy",
                    "error": "Missing Ubona fields: " + ", ".join(missing),
                }

            health_url = api_url.strip()
            headers = {
                "X-API-KEY": api_key,
            }

            try:
                resp = requests.get(health_url, headers=headers, timeout=10)
            except requests.RequestException as e:
                logger.error(f"Ubona Bot API health request failed: {e}")
                return {
                    "status": "unhealthy",
                    "error": f"Failed to reach Ubona API: {e}",
                }

            if resp.status_code == 200:
                return {
                    "status": "connected",
                    "details": "Ubona bot credentials valid (health endpoint returned 200)",
                }
            elif resp.status_code in (401, 403):
                return {
                    "status": "unhealthy",
                    "error": f"Invalid Ubona credentials or access forbidden (HTTP {resp.status_code}).",
                }
            else:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text

                logger.error(f"Ubona bot health check HTTP {resp.status_code}: {body}")
                return {
                    "status": "unhealthy",
                    "error": f"Ubona health check failed with HTTP {resp.status_code}: {body}",
                }

        except Exception as e:
            logger.error(f"Ubona bot health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# ============================================================
#  HOUSE OF AGENTS SERVICE
# ============================================================

class HouseOfAgentsService(BaseBotCallingService):
    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        # TODO: implement real HOA bot call
        raise BotCallApiException("House of Agents bot call not implemented yet.")

    def health_check(self) -> Dict[str, Any]:
        """
        Health check for House of Agents:

        - Requires: API Key, API URL, Agent ID
        - GET API URL with header X-API-KEY
        """
        try:
            api_key = self.credentials.get("hoa_api_key")
            api_url = self.credentials.get("hoa_api_url")
            agent_id = self.credentials.get("hoa_agent_id")

            missing = []
            if not api_key:
                missing.append("API Key")
            if not api_url:
                missing.append("API URL")
            if not agent_id:
                missing.append("Agent ID")

            if missing:
                return {
                    "status": "unhealthy",
                    "error": "Missing House of Agents fields: " + ", ".join(missing),
                }

            url = api_url.strip()
            headers = {
                "X-API-KEY": api_key,
                "X-AGENT-ID": agent_id,
            }

            try:
                resp = requests.get(url, headers=headers, timeout=10)
            except requests.RequestException as e:
                logger.error(f"House of Agents API health request failed: {e}")
                return {
                    "status": "unhealthy",
                    "error": f"Failed to reach House of Agents API: {e}",
                }

            if resp.status_code == 200:
                return {
                    "status": "connected",
                    "details": "House of Agents credentials valid",
                }
            elif resp.status_code in (401, 403):
                return {
                    "status": "unhealthy",
                    "error": f"Invalid HOA credentials or access forbidden (HTTP {resp.status_code}).",
                }
            else:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text

                logger.error(f"HOA health check HTTP {resp.status_code}: {body}")
                return {
                    "status": "unhealthy",
                    "error": f"HOA health check failed with HTTP {resp.status_code}: {body}",
                }

        except Exception as e:
            logger.error(f"House of Agents bot health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# ============================================================
#  GNANI.AI BOT SERVICE
# ============================================================

class GnaniAiBotService(BaseBotCallingService):
    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        # TODO: implement real Gnani.ai bot call
        raise BotCallApiException("Gnani.ai bot call not implemented yet.")

    def health_check(self) -> Dict[str, Any]:
        """
        Health check for Gnani.ai:

        - Requires: API Key, API URL, Bot ID, Project ID
        - GET API URL with header X-API-KEY
        """
        try:
            api_key = self.credentials.get("gnani_api_key")
            api_url = self.credentials.get("gnani_api_url")
            bot_id = self.credentials.get("gnani_bot_id")
            project_id = self.credentials.get("gnani_project_id")

            missing = []
            if not api_key:
                missing.append("API Key")
            if not api_url:
                missing.append("API URL")
            if not bot_id:
                missing.append("Bot ID")
            if not project_id:
                missing.append("Project ID")

            if missing:
                return {
                    "status": "unhealthy",
                    "error": "Missing Gnani.ai fields: " + ", ".join(missing),
                }

            url = api_url.strip()
            headers = {
                "X-API-KEY": api_key,
                "X-BOT-ID": bot_id,
                "X-PROJECT-ID": project_id,
            }

            try:
                resp = requests.get(url, headers=headers, timeout=10)
            except requests.RequestException as e:
                logger.error(f"Gnani.ai API health request failed: {e}")
                return {
                    "status": "unhealthy",
                    "error": f"Failed to reach Gnani.ai API: {e}",
                }

            if resp.status_code == 200:
                return {
                    "status": "connected",
                    "details": "Gnani.ai credentials valid",
                }
            elif resp.status_code in (401, 403):
                return {
                    "status": "unhealthy",
                    "error": f"Invalid Gnani.ai credentials or access forbidden (HTTP {resp.status_code}).",
                }
            else:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text

                logger.error(f"Gnani.ai health check HTTP {resp.status_code}: {body}")
                return {
                    "status": "unhealthy",
                    "error": f"Gnani.ai health check failed with HTTP {resp.status_code}: {body}",
                }

        except Exception as e:
            logger.error(f"Gnani.ai bot health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# ============================================================
#  TWILIO VOICE BOT SERVICE
# ============================================================

class TwilioVoiceBotService(BaseBotCallingService):
    def make_call(self, to_number: str, **kwargs) -> Dict[str, Any]:
        # TODO: implement real Twilio voice bot call
        raise BotCallApiException("Twilio voice bot call not implemented yet.")

    def health_check(self) -> Dict[str, Any]:
        """
        Health check for Twilio Voice Bot (same logic as normal call Twilio):

        - Missing credentials           => 'unhealthy'
        - Invalid credentials (401/403) => 'unhealthy'
        - Other errors                  => 'unhealthy'
        - Valid credentials             => 'connected'
        """
        account_sid = self.credentials.get("twilio_account_sid")
        auth_token = self.credentials.get("twilio_auth_token")

        if not account_sid or not auth_token:
            return {
                "status": "unhealthy",
                "error": "Twilio credentials (Account SID or Auth Token) are not configured.",
            }

        try:
            client = Client(account_sid, auth_token)
            client.api.v2010.accounts(account_sid).fetch()

            return {
                "status": "connected",
                "details": "Twilio bot credentials valid",
            }

        except TwilioRestException as e:
            logger.error(f"Twilio Voice Bot API Error (health check): {e}")

            status_code = getattr(e, "status", None)
            if status_code in (401, 403):
                msg = "Invalid Twilio Account SID or Auth Token."
            else:
                msg = str(e)

            return {
                "status": "unhealthy",
                "error": msg,
            }

        except Exception as e:
            logger.error(f"Twilio Voice Bot health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# ============================================================
#  FACTORY + PUBLIC SERVICE (BotCallingProviderService)
# ============================================================

class BotCallingProviderService:
    """
    Factory + helper for BOT-calling providers.

    - PROVIDER_MAP
    - _get_provider_class
    - get_service_instance
    - test_provider
    - check_provider_health
    """

    PROVIDER_MAP: Dict[str, Type[BaseBotCallingService]] = {
        "ubona_bot_calling": UbonaBotCallingService,
        "house_of_agents":   HouseOfAgentsService,
        "gnani_ai_bot":      GnaniAiBotService,
        "twilio_voice_bot":  TwilioVoiceBotService,
    }

    def __init__(self):
        self.encryption_key = getattr(settings, "BOT_CALLING_ENCRYPTION_KEY", None)

    # ---------- encryption for serializers ----------

    def _encrypt_credential(self, value: str) -> str:
        """
        Encrypt a credential using BOT_CALLING_ENCRYPTION_KEY.
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

    def _get_provider_class(self, provider_type: str) -> Optional[Type[BaseBotCallingService]]:
        """Returns the correct service class based on the provider type."""
        return self.PROVIDER_MAP.get(provider_type)

    def get_service_instance(self, provider_id: int = None) -> BaseBotCallingService:
        """
        Gets an instance of the correct provider service.
        If provider_id is None, fetch the 'default' bot provider.
        """
        try:
            if provider_id:
                provider_model = BotCallingProviderConfig.objects.get(
                    id=provider_id,
                    is_active=True,
                    is_deleted=False,
                )
            else:
                logger.info("No bot provider ID given, fetching default BOT-calling provider.")
                provider_model = BotCallingProviderConfig.objects.get(
                    is_default=True,
                    is_active=True,
                    is_deleted=False,
                )
        except BotCallingProviderConfig.DoesNotExist:
            logger.error(f"No active BOT provider found for ID: {provider_id} or as default.")
            raise BotCallApiException("No active or default BOT-calling provider configured.")
        except BotCallingProviderConfig.MultipleObjectsReturned:
            logger.error("Multiple default BOT providers found. Please set only one default.")
            raise BotCallApiException("Multiple default BOT providers found.")

        ProviderClass = self._get_provider_class(provider_model.provider_type)

        if not ProviderClass:
            logger.error(f"No service class found for BOT provider type: {provider_model.provider_type}")
            raise BotCallApiException(f"Provider type {provider_model.provider_type} is not supported.")

        return ProviderClass(provider_model)

    # --------------------------------------------------------
    #  TEST PROVIDER (play button)
    # --------------------------------------------------------
    def test_provider(self, provider: BotCallingProviderConfig, test_number: str) -> Dict[str, Any]:
        """
        Called when you click the play button.
        For now: just simulate a bot call.
        """
        start = time.time()
        time.sleep(0.2)  # simulate network delay
        elapsed = round(time.time() - start, 3)

        return {
            "success": True,
            "message": f"Test bot call simulated for {test_number} using {provider.name}",
            "response_time": elapsed,
        }

    # --------------------------------------------------------
    #  HEALTH CHECK (used by /health_check and /health_status)
    # --------------------------------------------------------
    def check_provider_health(self, provider: BotCallingProviderConfig, user=None) -> Dict[str, Any]:
        """
        1. Build correct service (Ubona / HOA / Gnani / Twilio).
        2. Call service.health_check()
        3. Map result to success + status + details
        4. Call provider.update_status(...) to update DB + log
        5. Return dict for API response
        """
        start = time.time()

        try:
            service = self.get_service_instance(provider_id=provider.id)
        except BotCallApiException as e:
            logger.error(str(e))
            return {
                "success": False,
                "status": "unhealthy",
                "details": str(e),
                "response_time": 0.0,
            }

        result = service.health_check()
        status = result.get("status", "unhealthy")
        details = result.get("details") or result.get("error") or ""
        success = status == "connected"
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
            logger.error(f"Failed to update bot provider status for {provider.name}: {e}")

        return {
            "success": success,
            "status": status,
            "details": details,
            "response_time": response_time,
        }
