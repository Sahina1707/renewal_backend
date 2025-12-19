import logging

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import CallProviderConfig
from .services import CallProviderService

logger = logging.getLogger(__name__)


class TwilioStatusCallbackView(APIView):
    """
    Twilio will POST here with call status updates.

    Final URL (with project prefix) is:
    /call-provider/twilio/status-callback/<provider_id>/
    """

    permission_classes = [AllowAny]

    def post(self, request, provider_id: int, *args, **kwargs):
        provider = get_object_or_404(
            CallProviderConfig,
            id=provider_id,
            is_deleted=False,
        )

        # Twilio sends form-encoded fields by default
        call_sid = request.data.get("CallSid")
        call_status = request.data.get("CallStatus")     # queued, ringing, in-progress, completed, failed, busy, no-answer
        duration = request.data.get("CallDuration")      # seconds as string, only for completed

        terminal_statuses = {"completed", "failed", "busy", "no-answer", "canceled"}
        if call_status in terminal_statuses:
            success = call_status == "completed"

            try:
                CallProviderService.log_usage_for_provider(
                    provider=provider,
                    status=call_status,
                    success=success,
                    duration=float(duration) if duration else None,
                    extra={
                        "provider_type": "twilio",
                        "call_sid": call_sid,
                        "raw_payload": dict(request.data),
                    },
                )
            except Exception as exc:
                logger.exception(
                    "Failed to log Twilio callback for provider %s: %s",
                    provider.id, exc
                )

        # Always return 200 so Twilio is satisfied
        return Response("OK")


class ExotelStatusCallbackView(APIView):
    """
    Generic Exotel callback endpoint.

    Your Exotel integration (or a middle service) should POST here with
    at least a status + optional duration.

    Final URL:
    /call-provider/exotel/status-callback/<provider_id>/
    """

    permission_classes = [AllowAny]

    def post(self, request, provider_id: int, *args, **kwargs):
        provider = get_object_or_404(
            CallProviderConfig,
            id=provider_id,
            is_deleted=False,
        )

        status_str = (
            request.data.get("Status")
            or request.data.get("status")
            or request.data.get("CallStatus")
            or "unknown"
        )
        status_str = str(status_str).lower()

        duration = (
            request.data.get("CallDuration")
            or request.data.get("duration")
            or request.data.get("call_duration")
        )

        # you can adjust this mapping depending on actual Exotel payload
        success = status_str in {"completed", "answered", "success"}

        try:
            CallProviderService.log_usage_for_provider(
                provider=provider,
                status=status_str,
                success=success,
                duration=float(duration) if duration else None,
                extra={
                    "provider_type": "exotel",
                    "raw_payload": dict(request.data),
                },
            )
        except Exception as exc:
            logger.exception(
                "Failed to log Exotel callback for provider %s: %s",
                provider.id, exc
            )

        return Response("OK")


class UbonaStatusCallbackView(APIView):
    """
    Generic Ubona callback endpoint.

    Your Ubona integration (or a middle service) should POST here with
    normalised fields.

    Final URL:
    /call-provider/ubona/status-callback/<provider_id>/
    """

    permission_classes = [AllowAny]

    def post(self, request, provider_id: int, *args, **kwargs):
        provider = get_object_or_404(
            CallProviderConfig,
            id=provider_id,
            is_deleted=False,
        )

        status_str = (
            request.data.get("status")
            or request.data.get("Status")
            or "unknown"
        )
        status_str = str(status_str).lower()

        duration = (
            request.data.get("duration")
            or request.data.get("CallDuration")
            or request.data.get("call_duration")
        )

        success = status_str in {"completed", "answered", "success"}

        try:
            CallProviderService.log_usage_for_provider(
                provider=provider,
                status=status_str,
                success=success,
                duration=float(duration) if duration else None,
                extra={
                    "provider_type": "ubona",
                    "raw_payload": dict(request.data),
                },
            )
        except Exception as exc:
            logger.exception(
                "Failed to log Ubona callback for provider %s: %s",
                provider.id, exc
            )

        return Response("OK")
