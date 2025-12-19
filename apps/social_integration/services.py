import requests
import datetime
from django.utils import timezone
from .models import (
    SocialPlatform,
    SocialVerificationSettings,
    SocialVerificationResult,
    SocialIntegrationStatistics,
)


# ============================================================
# CUSTOM EXCEPTION
# ============================================================
class PlatformConnectionError(Exception):
    pass


# ============================================================
# PLATFORM VALIDATION HELPERS
# ============================================================
def validate_telegram(bot_token: str):
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        raise PlatformConnectionError("Invalid Telegram bot token")


def validate_whatsapp(api_token: str):
    url = "https://graph.facebook.com/v18.0/me"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise PlatformConnectionError("Invalid WhatsApp API token")


# ============================================================
# 1️⃣ SAVE PLATFORM CREDENTIALS + UPDATE CONNECT STATUS
# ============================================================
def save_platform_credentials(platform_name: str, credentials: dict) -> SocialPlatform:
    platform = SocialPlatform.objects.get(platform=platform_name)

    # --------------------------------------------------------
    # PLATFORM-SPECIFIC VALIDATION
    # --------------------------------------------------------
    if platform_name == "telegram":
        token = credentials.get("telegram_bot_token")
        if not token:
            raise PlatformConnectionError("Telegram bot token required")
        validate_telegram(token)

    elif platform_name == "whatsapp":
        token = credentials.get("whatsapp_api_key")
        if not token:
            raise PlatformConnectionError("WhatsApp API key required")
        validate_whatsapp(token)

    elif platform_name in [
        "facebook",
        "instagram",
        "twitter",
        "linkedin",
        "wechat",
        "line",
    ]:
        raise PlatformConnectionError(
            f"{platform_name} requires OAuth login. Manual credentials not allowed."
        )

    # --------------------------------------------------------
    # SAVE CREDENTIALS
    # --------------------------------------------------------
    for key, value in credentials.items():
        if hasattr(platform, key):
            setattr(platform, key, value)

    platform.is_connected = True
    platform.is_not_connected = False
    platform.last_connected_at = timezone.now()
    platform.last_error_message = None
    platform.save()

    return platform


# ============================================================
# 2️⃣ TEST VERIFICATION (NO CUSTOMER DATA STORED)
# ============================================================
def test_customer_verification(_payload: dict):
    """
    _payload is intentionally unused for now.

    🔹 Future:
    - Fetch customer from another table
    - Pass customer_id instead
    """

    settings = SocialVerificationSettings.objects.first()
    if not settings:
        settings = SocialVerificationSettings.objects.create()

    connected_platforms = SocialPlatform.objects.filter(is_connected=True)
    results = []

    for platform in connected_platforms:
        found = False
        verified = False

        # ⚠️ TEMPORARY REAL-TIME CHECK PLACEHOLDER
        # Replace this block with platform-specific API calls later
        raw_response = {
            "platform": platform.platform,
            "status": "checked",
            "note": "customer lookup will be added later",
        }

        # Current behaviour preserved
        found = platform.is_connected
        verified = found and settings.auto_connect_on_verification

        result = SocialVerificationResult.objects.create(
            platform=platform,
            is_found=found,
            is_verified=verified,
            raw_response=raw_response,
        )

        results.append(result)

    return results


# ============================================================
# 3️⃣ AUTO DELETE VERIFICATION DATA
# ============================================================
def apply_data_retention_cleanup():

    settings = SocialVerificationSettings.objects.first()
    if not settings or not settings.save_customer_data:
        return 0

    retention_map = {
        "90_days": 90,
        "6_months": 180,
        "1_year": 365,
        "2_years": 730,
        "3_years": 1095,
    }

    retention_days = retention_map.get(settings.retention_period, 365)
    cutoff_date = timezone.now() - datetime.timedelta(days=retention_days)

    deleted_count, _ = SocialVerificationResult.objects.filter(
        tested_at__lt=cutoff_date
    ).delete()

    return deleted_count


# ============================================================
# 4️⃣ UPDATE STATISTICS
# ============================================================
def generate_daily_statistics():

    connected_count = SocialPlatform.objects.filter(is_connected=True).count()
    verified_count = SocialVerificationResult.objects.filter(is_verified=True).count()
    found_count = SocialVerificationResult.objects.filter(is_found=True).count()

    rate = round((verified_count / found_count) * 100, 2) if found_count else 0

    stat = SocialIntegrationStatistics.objects.create(
        date=timezone.now().date(),
        period="daily",
        connected_platforms=connected_count,
        verified_customers=verified_count,
        social_connections=found_count,
        verification_rate=rate,
    )

    return stat
