from rest_framework import serializers
from .models import (
    SocialPlatform,
    SocialVerificationResult,
    SocialVerificationSettings,
    SocialIntegrationStatistics,
)


# ==========================================================
# 1️⃣ SOCIAL PLATFORM SERIALIZER
# ==========================================================
class SocialPlatformSerializer(serializers.ModelSerializer):

    class Meta:
        model = SocialPlatform
        fields = [
            "id",
            "platform",
            "display_name",

            # Facebook
            "facebook_api_key",
            "facebook_api_secret",
            "facebook_page_id",
            "facebook_access_token",

            # Twitter
            "twitter_api_key",
            "twitter_api_secret",
            "twitter_access_token",
            "twitter_access_token_secret",

            # Instagram
            "instagram_business_account_id",
            "instagram_access_token",
            "instagram_app_id",
            "instagram_app_secret",

            # LinkedIn
            "linkedin_client_id",
            "linkedin_client_secret",
            "linkedin_access_token",
            "linkedin_company_id",

            # WeChat
            "wechat_app_id",
            "wechat_app_secret",
            "wechat_merchant_id",
            "wechat_api_key",

            # LINE
            "line_channel_id",
            "line_channel_secret",
            "line_channel_access_token",

            # Telegram
            "telegram_bot_token",
            "telegram_chat_id",
            "telegram_webhook_url",

            # Connection state
            "is_connected",
            "is_not_connected",
            "last_connected_at",
            "last_error_message",

            "created_at",
            "updated_at",
        ]

        read_only_fields = (
            "is_connected",
            "is_not_connected",
            "last_connected_at",
            "last_error_message",
            "created_at",
            "updated_at",
        )


# ==========================================================
# 2️⃣ CONNECT PLATFORM SERIALIZER
# ==========================================================
class SocialPlatformConnectSerializer(serializers.Serializer):

    facebook_api_key = serializers.CharField(required=False, allow_blank=True)
    facebook_api_secret = serializers.CharField(required=False, allow_blank=True)
    facebook_page_id = serializers.CharField(required=False, allow_blank=True)
    facebook_access_token = serializers.CharField(required=False, allow_blank=True)

    twitter_api_key = serializers.CharField(required=False, allow_blank=True)
    twitter_api_secret = serializers.CharField(required=False, allow_blank=True)
    twitter_access_token = serializers.CharField(required=False, allow_blank=True)
    twitter_access_token_secret = serializers.CharField(required=False, allow_blank=True)

    instagram_business_account_id = serializers.CharField(required=False, allow_blank=True)
    instagram_access_token = serializers.CharField(required=False, allow_blank=True)
    instagram_app_id = serializers.CharField(required=False, allow_blank=True)
    instagram_app_secret = serializers.CharField(required=False, allow_blank=True)

    linkedin_client_id = serializers.CharField(required=False, allow_blank=True)
    linkedin_client_secret = serializers.CharField(required=False, allow_blank=True)
    linkedin_access_token = serializers.CharField(required=False, allow_blank=True)
    linkedin_company_id = serializers.CharField(required=False, allow_blank=True)

    wechat_app_id = serializers.CharField(required=False, allow_blank=True)
    wechat_app_secret = serializers.CharField(required=False, allow_blank=True)
    wechat_merchant_id = serializers.CharField(required=False, allow_blank=True)
    wechat_api_key = serializers.CharField(required=False, allow_blank=True)

    line_channel_id = serializers.CharField(required=False, allow_blank=True)
    line_channel_secret = serializers.CharField(required=False, allow_blank=True)
    line_channel_access_token = serializers.CharField(required=False, allow_blank=True)

    telegram_bot_token = serializers.CharField(required=False, allow_blank=True)
    telegram_chat_id = serializers.CharField(required=False, allow_blank=True)
    telegram_webhook_url = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one credential must be provided."
            )
        return attrs


# ==========================================================
# 3️⃣ VERIFICATION RESULT SERIALIZER
# ==========================================================
class SocialVerificationResultSerializer(serializers.ModelSerializer):

    class Meta:
        model = SocialVerificationResult
        fields = [
            "id",
            "platform",
            "is_found",
            "is_verified",
            "profile_url",
            "raw_response",
            "tested_at",
        ]


# ==========================================================
# 4️⃣ GLOBAL SETTINGS SERIALIZER (VERSIONED)
# ==========================================================
class SocialVerificationSettingsSerializer(serializers.ModelSerializer):

    class Meta:
        model = SocialVerificationSettings
        fields = (
            "id",
            "enable_social_verification",
            "auto_connect_on_verification",
            "save_customer_data",
            "retention_period",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


# ==========================================================
# 5️⃣ STATISTICS SERIALIZER
# ==========================================================
class SocialIntegrationStatisticsSerializer(serializers.ModelSerializer):

    class Meta:
        model = SocialIntegrationStatistics
        fields = "__all__"
