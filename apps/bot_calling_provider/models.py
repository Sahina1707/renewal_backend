from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
class BotCallingProviderConfig(models.Model):
    """Configuration for bot-calling providers."""

    PROVIDER_CHOICES = [
        ("ubona_bot", "Ubona Bot Calling"),
        ("house_of_agents", "House of Agents"),
        ("gnani_bot", "Gnani.ai Bot"),
        ("twilio_voice_bot", "Twilio Voice Bot"),
    ]

    PRIORITY_CHOICES = [
        (1, "Primary"),
        (2, "Secondary"),
        (3, "Tertiary"),
    ]

    STATUS_CHOICES = [
        ("connected", "Connected"),
        ("disconnected", "Disconnected"),
        ("error", "Error"),
        ("unknown", "Unknown"),
    ]

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(
        max_length=100,
        help_text="Friendly name for this bot provider, e.g. Ubona Bot",
    )
    provider_type = models.CharField(max_length=30, choices=PROVIDER_CHOICES)

    bot_script = models.TextField(
        blank=True,
        null=True,
        help_text="Bot script / prompt used by this provider",
    )

    ubona_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Ubona Bot API Key (encrypted)",
    )
    ubona_account_sid = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Ubona Bot Account SID / project id",
    )
    ubona_api_url = models.URLField(
        blank=True,
        null=True,
        help_text="Ubona Bot API URL",
    )
    ubona_caller_id = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Ubona Bot Caller ID",
    )

    hoa_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="House of Agents API Key (encrypted)",
    )
    hoa_api_url = models.URLField(
        blank=True,
        null=True,
        help_text="House of Agents API URL",
    )
    hoa_agent_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="House of Agents Agent ID",
    )
    hoa_campaign_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="House of Agents Campaign ID",
    )
    hoa_webhook_url = models.URLField(
        blank=True,
        null=True,
        help_text="House of Agents Webhook URL",
    )

    gnani_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Gnani.ai API Key (encrypted)",
    )
    gnani_api_url = models.URLField(
        blank=True,
        null=True,
        help_text="Gnani.ai API URL",
    )
    gnani_bot_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Gnani.ai Bot ID",
    )
    gnani_project_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Gnani.ai Project ID",
    )
    gnani_language = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Language code for Gnani.ai bot",
    )
    gnani_voice_gender = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Voice gender (e.g. male/female)",
    )

    twilio_account_sid = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Twilio Account SID (encrypted)",
    )
    twilio_auth_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Twilio Auth Token (encrypted)",
    )
    twilio_from_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Twilio caller number in E.164 format",
    )
    twilio_status_callback_url = models.URLField(
        blank=True,
        null=True,
        help_text="Twilio status callback URL for bot calls",
    )
    twilio_voice_url = models.URLField(
        blank=True,
        null=True,
        help_text="Twilio Voice URL / TwiML URL for bot",
    )

    daily_limit = models.PositiveIntegerField(
        default=1000,
        help_text="Daily bot call limit",
    )
    monthly_limit = models.PositiveIntegerField(
        default=30000,
        help_text="Monthly bot call limit",
    )
    rate_limit_per_minute = models.PositiveIntegerField(
        default=10,
        help_text="Rate limit per minute",
    )

    priority = models.PositiveIntegerField(
        choices=PRIORITY_CHOICES,
        default=1,
        help_text="Priority order when selecting bot provider",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    last_health_check = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        default="unknown",
        choices=STATUS_CHOICES,
        help_text="Connection status (connected / disconnected / error / unknown)",
    )

    calls_made_today = models.PositiveIntegerField(default=0)
    calls_made_this_month = models.PositiveIntegerField(default=0)
    last_reset_daily = models.DateField(default=timezone.now)
    last_reset_monthly = models.DateField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bot_calling_providers",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bot_calling_providers",
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_bot_calling_providers",
    )

    class Meta:
        db_table = "bot_calling_provider_configs"
        ordering = ["priority", "name"]
        verbose_name = "Bot Calling Provider Configuration"
        verbose_name_plural = "Bot Calling Provider Configurations"

    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"

    def update_status(
        self,
        is_healthy: bool,
        error_message: str = None,
        response_time: float = None,
        test_type: str = "health_check",
        user=None,
    ):

        self.last_health_check = timezone.now()

        if not self.is_active:
            self.status = "disconnected"
        else:
            self.status = "connected" if is_healthy else "error"

        self.save(update_fields=["last_health_check", "status"])

        BotCallingProviderHealthLog.objects.create(
            provider=self,
            is_healthy=is_healthy,
            error_message=error_message or "",
            response_time=response_time or 0.0,
            status="active",
            test_type=test_type,
            created_by=user,
            updated_by=user,
        )

    def can_make_call(self) -> bool:
        if not self.is_active or self.status in ["error", "disconnected"]:
            return False
        if self.calls_made_today >= self.daily_limit:
            return False
        if self.calls_made_this_month >= self.monthly_limit:
            return False
        return True

    def increment_usage(self, count: int = 1):
        self.calls_made_today += count
        self.calls_made_this_month += count
        self.save(update_fields=["calls_made_today", "calls_made_this_month"])

    def reset_daily_usage(self):
        self.calls_made_today = 0
        self.last_reset_daily = timezone.now().date()
        self.save(update_fields=["calls_made_today", "last_reset_daily"])

    def reset_monthly_usage(self):
        self.calls_made_this_month = 0
        self.last_reset_monthly = timezone.now().date()
        self.save(update_fields=["calls_made_this_month", "last_reset_monthly"])

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["is_deleted", "deleted_at", "is_active"])

class BotCallingProviderHealthLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        BotCallingProviderConfig,
        on_delete=models.CASCADE,
        related_name="health_logs",
    )
    is_healthy = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    response_time = models.FloatField(
        default=0.0,
        help_text="Response time in seconds",
    )
    checked_at = models.DateTimeField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default="active")
    test_type = models.CharField(max_length=50, blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bot_calling_health_logs",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bot_calling_health_logs",
    )
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_bot_calling_health_logs",
    )
    class Meta:
        db_table = "bot_calling_provider_health_logs"
        ordering = ["-checked_at"]
        verbose_name = "Bot Calling Provider Health Log"
        verbose_name_plural = "Bot Calling Provider Health Logs"

    def __str__(self):
        status = "Healthy" if self.is_healthy else "Error"
        return f"{self.provider.name} - {status} ({self.checked_at})"

class BotCallingProviderUsageLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        BotCallingProviderConfig,
        on_delete=models.CASCADE,
        related_name="usage_logs",
    )
    calls_made = models.PositiveIntegerField()
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    total_response_time = models.FloatField(
        default=0.0,
        help_text="Total API response time in seconds",
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bot_calling_usage_logs",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bot_calling_usage_logs",
    )
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_bot_calling_usage_logs",
    )

    class Meta:
        db_table = "bot_calling_provider_usage_logs"
        ordering = ["-logged_at"]
        verbose_name = "Bot Calling Provider Usage Log"
        verbose_name_plural = "Bot Calling Provider Usage Logs"

    def __str__(self):
        return f"{self.provider.name} - {self.calls_made} calls ({self.logged_at})"
class BotCallingProviderTestResult(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    provider = models.ForeignKey(
        BotCallingProviderConfig,
        on_delete=models.CASCADE,
        related_name="test_results",
    )
    test_number = models.CharField(
        max_length=20,
        help_text="Destination phone number used for test",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    error_message = models.TextField(blank=True, null=True)
    response_time = models.FloatField(
        blank=True,
        null=True,
        help_text="API response time in seconds",
    )
    tested_at = models.DateTimeField(auto_now_add=True)
    tested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    status_text = models.CharField(max_length=20, default="active")
    test_type = models.CharField(max_length=50, blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bot_calling_test_logs",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bot_calling_test_logs",
    )
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_bot_calling_test_logs",
    )

    class Meta:
        db_table = "bot_calling_provider_test_results"
        ordering = ["-tested_at"]
        verbose_name = "Bot Calling Provider Test Result"
        verbose_name_plural = "Bot Calling Provider Test Results"

    def __str__(self):
        return f"{self.provider.name} test to {self.test_number} - {self.get_status_display()}"