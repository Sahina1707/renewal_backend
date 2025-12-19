from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

from .models import (
    SocialPlatform,
    SocialVerificationSettings,
)

from .serializers import (
    SocialPlatformSerializer,
    SocialPlatformConnectSerializer,
    SocialVerificationSettingsSerializer,
    SocialVerificationResultSerializer,
)

from .services import (
    save_platform_credentials,
    test_customer_verification,
    generate_daily_statistics,
    PlatformConnectionError,
)


# ============================================================
# 1️⃣ PLATFORM VIEWSET
# ============================================================
class SocialPlatformViewSet(viewsets.ModelViewSet):
    queryset = SocialPlatform.objects.all()
    serializer_class = SocialPlatformSerializer

    @action(detail=True, methods=["post"], url_path="connect")
    def connect(self, request, pk=None):

        platform = get_object_or_404(SocialPlatform, pk=pk)
        serializer = SocialPlatformConnectSerializer(data=request.data)

        if serializer.is_valid():
            try:
                save_platform_credentials(
                    platform.platform,
                    serializer.validated_data
                )

                platform.refresh_from_db()

                return Response(
                    SocialPlatformSerializer(platform).data,
                    status=status.HTTP_200_OK
                )

            except PlatformConnectionError as e:
                platform.is_connected = False
                platform.is_not_connected = True
                platform.last_error_message = str(e)
                platform.save()

                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# 2️⃣ SOCIAL VERIFICATION SETTINGS (VERSIONED)
# ============================================================
class SocialVerificationSettingsView(APIView):

    def get(self, request):
        """
        Always return latest settings
        """
        settings = SocialVerificationSettings.objects.order_by("-id").first()

        if not settings:
            settings = SocialVerificationSettings.objects.create(
                enable_social_verification=True,
                auto_connect_on_verification=False,
                save_customer_data=True,
                retention_period="1_year",
            )

        serializer = SocialVerificationSettingsSerializer(settings)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a NEW row for every change (versioned settings)
        """
        latest = SocialVerificationSettings.objects.order_by("-id").first()

        new_settings = SocialVerificationSettings.objects.create(
            enable_social_verification=request.data.get(
                "enable_social_verification",
                latest.enable_social_verification if latest else True
            ),
            auto_connect_on_verification=request.data.get(
                "auto_connect_on_verification",
                latest.auto_connect_on_verification if latest else False
            ),
            save_customer_data=request.data.get(
                "save_customer_data",
                latest.save_customer_data if latest else True
            ),
            retention_period=request.data.get(
                "retention_period",
                latest.retention_period if latest else "1_year"
            ),
        )

        serializer = SocialVerificationSettingsSerializer(new_settings)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ============================================================
# 3️⃣ TEST SOCIAL VERIFICATION (REAL-TIME)
# ============================================================
class SocialVerificationTestView(APIView):

    def post(self, request):
        """
        Body example (temporary):
        {
            "phone": "9876543210",
            "email": "test@example.com"
        }
        """

        results = test_customer_verification(request.data)
        serializer = SocialVerificationResultSerializer(results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================
# 4️⃣ STATISTICS
# ============================================================
class SocialIntegrationStatisticsView(APIView):

    def get(self, request):

        stats = generate_daily_statistics()

        return Response({
            "connected_platforms": stats.connected_platforms,
            "verified_customers": stats.verified_customers,
            "social_connections": stats.social_connections,
            "verification_rate": stats.verification_rate,
            "date": stats.date,
        }, status=status.HTTP_200_OK)
