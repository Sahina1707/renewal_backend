from django.contrib import admin
from .models import (
    SocialPlatform,
    SocialVerificationSettings,
    SocialVerificationResult,
    SocialIntegrationStatistics,
)


# ================================================================
# 1️⃣ PLATFORM ADMIN
# ================================================================
@admin.register(SocialPlatform)
class SocialPlatformAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "platform",
        "is_connected",
        "is_not_connected",
        "last_connected_at",
        "created_at",
    )

    list_filter = ("platform", "is_connected")
    search_fields = ("platform",)
    readonly_fields = ("created_at", "updated_at", "last_connected_at")

    fieldsets = (
        ("Basic Info", {
            "fields": ("platform", "display_name")
        }),

        ("Connection Status", {
            "fields": (
                "is_connected",
                "is_not_connected",
                "last_connected_at",
                "last_error_message",
            )
        }),

        ("Facebook Credentials", {
            "fields": (
                "facebook_api_key",
                "facebook_api_secret",
                "facebook_page_id",
                "facebook_access_token",
            )
        }),

        ("Twitter Credentials", {
            "fields": (
                "twitter_api_key",
                "twitter_api_secret",
                "twitter_access_token",
                "twitter_access_token_secret",
            )
        }),

        ("Instagram Credentials", {
            "fields": (
                "instagram_business_account_id",
                "instagram_access_token",
                "instagram_app_id",
                "instagram_app_secret",
            )
        }),

        ("LinkedIn Credentials", {
            "fields": (
                "linkedin_client_id",
                "linkedin_client_secret",
                "linkedin_access_token",
                "linkedin_company_id",
            )
        }),

        ("WeChat Credentials", {
            "fields": (
                "wechat_app_id",
                "wechat_app_secret",
                "wechat_merchant_id",
                "wechat_api_key",
            )
        }),

        ("LINE Credentials", {
            "fields": (
                "line_channel_id",
                "line_channel_secret",
                "line_channel_access_token",
            )
        }),

        ("Telegram Credentials", {
            "fields": (
                "telegram_bot_token",
                "telegram_chat_id",
                "telegram_webhook_url",
            )
        }),

        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )


# ================================================================
# 2️⃣ GLOBAL SETTINGS ADMIN
# ================================================================
@admin.register(SocialVerificationSettings)
class SocialVerificationSettingsAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "enable_social_verification",
        "auto_connect_on_verification",
        "save_customer_data",
        "retention_period",
        "updated_at",
    )

    list_editable = (
        "enable_social_verification",
        "auto_connect_on_verification",
        "save_customer_data",
        "retention_period",
    )


# ================================================================
# 3️⃣ VERIFICATION RESULT ADMIN
# ================================================================
@admin.register(SocialVerificationResult)
class SocialVerificationResultAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "platform",
        "is_found",
        "is_verified",
        "tested_at",
    )

    list_filter = ("platform", "is_found", "is_verified")
    readonly_fields = ("tested_at", "raw_response")


# ================================================================
# 4️⃣ STATISTICS ADMIN
# ================================================================
@admin.register(SocialIntegrationStatistics)
class SocialIntegrationStatisticsAdmin(admin.ModelAdmin):

    list_display = (
        "date",
        "period",
        "connected_platforms",
        "verified_customers",
        "social_connections",
        "verification_rate",
        "created_at",
    )

    list_filter = ("date", "period")
    readonly_fields = ("created_at",)
