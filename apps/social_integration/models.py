from django.db import models
from django.utils import timezone


# ===========================================================
# 1️⃣ MAIN TABLE — SOCIAL MEDIA PLATFORMS (7 platforms)
# ===========================================================
class SocialPlatform(models.Model):

    PLATFORM_CHOICES = [
        ("facebook", "Facebook"),
        ("twitter", "Twitter / X"),
        ("instagram", "Instagram"),
        ("linkedin", "LinkedIn"),
        ("wechat", "WeChat"),
        ("line", "LINE"),
        ("telegram", "Telegram"),
    ]

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)

    # ======================================================
    # FACEBOOK FIELDS
    # ======================================================
    facebook_api_key = models.TextField(blank=True, null=True)
    facebook_api_secret = models.TextField(blank=True, null=True)
    facebook_page_id = models.CharField(max_length=255, blank=True, null=True)
    facebook_access_token = models.TextField(blank=True, null=True)

    # ======================================================
    # TWITTER FIELDS
    # ======================================================
    twitter_api_key = models.TextField(blank=True, null=True)
    twitter_api_secret = models.TextField(blank=True, null=True)
    twitter_access_token = models.TextField(blank=True, null=True)
    twitter_access_token_secret = models.TextField(blank=True, null=True)

    # ======================================================
    # INSTAGRAM FIELDS
    # ======================================================
    instagram_business_account_id = models.CharField(max_length=255, blank=True, null=True)
    instagram_access_token = models.TextField(blank=True, null=True)
    instagram_app_id = models.CharField(max_length=255, blank=True, null=True)
    instagram_app_secret = models.TextField(blank=True, null=True)

    # ======================================================
    # LINKEDIN FIELDS
    # ======================================================
    linkedin_client_id = models.CharField(max_length=255, blank=True, null=True)
    linkedin_client_secret = models.CharField(max_length=255, blank=True, null=True)
    linkedin_access_token = models.TextField(blank=True, null=True)
    linkedin_company_id = models.CharField(max_length=255, blank=True, null=True)

    # ======================================================
    # WECHAT FIELDS
    # ======================================================
    wechat_app_id = models.CharField(max_length=255, blank=True, null=True)
    wechat_app_secret = models.CharField(max_length=255, blank=True, null=True)
    wechat_merchant_id = models.CharField(max_length=255, blank=True, null=True)
    wechat_api_key = models.CharField(max_length=255, blank=True, null=True)

    # ======================================================
    # LINE FIELDS
    # ======================================================
    line_channel_id = models.CharField(max_length=255, blank=True, null=True)
    line_channel_secret = models.CharField(max_length=255, blank=True, null=True)
    line_channel_access_token = models.TextField(blank=True, null=True)

    # ======================================================
    # TELEGRAM FIELDS
    # ======================================================
    telegram_bot_token = models.TextField(blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=255, blank=True, null=True)
    telegram_webhook_url = models.CharField(max_length=300, blank=True, null=True)

    # ======================================================
    # COMMON FIELDS
    # ======================================================
    is_connected = models.BooleanField(default=False)
    is_not_connected = models.BooleanField(default=True)

    last_connected_at = models.DateTimeField(blank=True, null=True)
    last_error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_connected(self):
        self.is_connected = True
        self.is_not_connected = False
        self.last_connected_at = timezone.now()
        self.save()

    def set_disconnected(self):
        self.is_connected = False
        self.is_not_connected = True
        self.save()

    def __str__(self):
        return self.display_name


# ===========================================================
# 2️⃣ CUSTOMER-SPECIFIC VERIFICATION RESULTS TABLE
# (Customer data intentionally NOT stored here)
# ===========================================================
class SocialVerificationResult(models.Model):

    platform = models.ForeignKey(
        SocialPlatform,
        on_delete=models.CASCADE,
        related_name="verifications"
    )

    is_found = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    profile_url = models.CharField(max_length=300, blank=True, null=True)
    raw_response = models.JSONField(blank=True, null=True)

    tested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.platform.display_name} | Found={self.is_found}"


# ===========================================================
# 3️⃣ GLOBAL VERIFICATION SETTINGS
# ===========================================================
class SocialVerificationSettings(models.Model):

    RETENTION_CHOICES = [
        ("90_days", "90 Days"),
        ("6_months", "6 Months"),
        ("1_year", "1 Year"),
        ("2_years", "2 Years"),
        ("3_years", "3 Years"),
    ]

    enable_social_verification = models.BooleanField(default=True)
    auto_connect_on_verification = models.BooleanField(default=False)
    save_customer_data = models.BooleanField(default=True)

    retention_period = models.CharField(
        max_length=20,
        choices=RETENTION_CHOICES,
        default="1_year"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Social Media Verification Settings"


# ===========================================================
# 4️⃣ STATISTICS TABLE
# ===========================================================
class SocialIntegrationStatistics(models.Model):

    date = models.DateField()
    period = models.CharField(max_length=20, default="daily")

    connected_platforms = models.IntegerField(default=0)
    verified_customers = models.IntegerField(default=0)
    social_connections = models.IntegerField(default=0)
    verification_rate = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Stats for {self.date} ({self.period})"
