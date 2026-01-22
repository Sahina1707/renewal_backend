import qrcode
import base64
from io import BytesIO
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import UserSettings
from .serializers import UserSettingsSerializer
from django_otp.plugins.otp_totp.models import TOTPDevice

class GeneralSettingsViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSettingsSerializer

    def get_object(self):
        # Retrieve the settings for the current user
        obj, created = UserSettings.objects.get_or_create(user=self.request.user)
        return obj

    @action(detail=False, methods=['get', 'patch'])
    def my_settings(self, request):
        """
        GET: Returns current settings (Frontend uses this to set initial toggle states).
        PATCH: Updates changed settings (Frontend calls this when 'Save' is clicked).
        """
        settings_obj = self.get_object()

        if request.method == 'GET':
            serializer = self.get_serializer(settings_obj)
            return Response(serializer.data)

        elif request.method == 'PATCH':
            serializer = self.get_serializer(settings_obj, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "status": "success", 
                    "message": "Settings updated successfully", 
                    "data": serializer.data
                })
            return Response(serializer.errors, status=400)


class MFAViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def generate_qr(self, request):
        """
        Step 1: Generate a Secret and a QR Code for the user to scan.
        """
        user = request.user
        
        # 1. Create a new unconfirmed device (or get existing one)
        # We filter for confirmed=False to avoid overwriting an active MFA device accidentally
        device, created = TOTPDevice.objects.get_or_create(user=user, confirmed=False, defaults={'name': 'default'})

        # 2. Generate the OTP URI (Standard format for Google Auth)
        otp_uri = device.config_url

        # 3. Generate QR Code Image
        qr = qrcode.make(otp_uri)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        return Response({
            "status": "pending",
            "message": "Scan this QR code with Google Authenticator",
            "qr_code_base64": f"data:image/png;base64,{qr_base64}",
            "manual_entry_key": base64.b32encode(device.bin_key).decode('utf-8') 
        })

    @action(detail=False, methods=['post'])
    def verify_and_enable(self, request):
        """
        Step 2: User enters the 6-digit code to confirm they scanned it.
        """
        user = request.user
        otp_code = request.data.get('otp')

        if not otp_code:
            return Response({"error": "OTP code is required"}, status=400)

        # 1. Find the unconfirmed device
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        
        if not device:
            return Response({"error": "No setup pending. Please generate QR first."}, status=400)

        # 2. Verify the Token
        if device.verify_token(otp_code):
            # Success! Mark device as confirmed
            device.confirmed = True
            device.save()
            
            # Update your UserSettings model to reflect the toggle is ON
            settings, _ = UserSettings.objects.get_or_create(user=user)
            settings.mfa_enabled = True
            settings.save()

            return Response({"status": "success", "message": "MFA Enabled Successfully"})
        
        return Response({"error": "Invalid OTP Code"}, status=400)

    @action(detail=False, methods=['post'])
    def disable(self, request):
        """
        Turn off MFA (User just toggles the switch OFF)
        """
        user = request.user
        
        # Delete all devices for this user
        TOTPDevice.objects.filter(user=user).delete()
        
        # Update Settings
        settings, _ = UserSettings.objects.get_or_create(user=user)
        settings.mfa_enabled = False
        settings.save()
        
        return Response({"status": "success", "message": "MFA Disabled"})