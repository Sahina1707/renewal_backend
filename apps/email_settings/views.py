import imaplib
import smtplib
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .utils import PROVIDER_DEFAULTS
from .utils import test_account_connection
from django.utils import timezone 
from .models import EmailAccount, EmailModuleSettings, ClassificationRule
from .serializers import EmailAccountSerializer, EmailModuleSettingsSerializer, ClassificationRuleSerializer
from .services import EmailSyncService
from rest_framework.decorators import action
# def check_imap_connection(server, port, email, credential, use_ssl):
#     """Checks the IMAP connection (Incoming Mail)."""
#     try:
#         if use_ssl:
#             M = imaplib.IMAP4_SSL(server, port)
#         else:
#             M = imaplib.IMAP4(server, port)
        
#         # Attempt login
#         M.login(email, credential)
#         M.logout()
#         return True, "IMAP connection successful."
#     except imaplib.IMAP4.error as e:
#         return False, f"IMAP login failed: {str(e)}"
#     except Exception as e:
#         return False, f"IMAP connection error: {str(e)}"

# def check_smtp_connection(server, port, email, credential, use_ssl):
#     """Checks the SMTP connection (Outgoing Mail)."""
#     try:
#         if use_ssl:
#             if port == 465:
#                 # Implicit SSL/TLS on port 465
#                 S = smtplib.SMTP_SSL(server, port, timeout=10)
#             else:
#                 # Explicit STARTTLS on other ports (e.g., 587)
#                 S = smtplib.SMTP(server, port, timeout=10)
#                 S.starttls()
#         else:
#             # Unencrypted connection
#             S = smtplib.SMTP(server, port, timeout=10)
        
#         S.ehlo()
#         S.login(email, credential)
#         S.quit()
#         return True, "SMTP connection successful."
#     except smtplib.SMTPAuthenticationError:
#         return False, "SMTP authentication failed (invalid credential)."
#     except smtplib.SMTPConnectError:
#         return False, "SMTP connection failed (server or port error)."
#     except Exception as e:
#         return False, f"SMTP connection error: {str(e)}"

# def test_account_connection(account_instance):
#     """Tests both IMAP and SMTP connection using the EmailAccount instance data."""
    
#     # FIX: Remove spaces from the credential before using it
#     credential = "".join(account_instance.access_credential.split()) if account_instance.access_credential else ""

#     # 1. Test IMAP
#     imap_success, imap_message = check_imap_connection(
#         account_instance.imap_server, 
#         account_instance.imap_port, 
#         account_instance.email_address, 
#         credential, 
#         account_instance.use_ssl_tls
#     )

#     # 2. Test SMTP
#     smtp_success, smtp_message = check_smtp_connection(
#         account_instance.smtp_server, 
#         account_instance.smtp_port, 
#         account_instance.email_address, 
#         credential, 
#         account_instance.use_ssl_tls
#     )

#     return {
#         "success": imap_success and smtp_success,
#         "imap_status": imap_message,
#         "smtp_status": smtp_message,
#     }

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, EmailModuleSettings):
            return obj.user_id == request.user.id
        return obj.user == request.user

class EmailAccountViewSet(viewsets.ModelViewSet):
    serializer_class = EmailAccountSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    @action(detail=True, methods=['post'], url_path='set-sync')
    def set_sync_status(self, request, pk=None):
        """
        Dedicated endpoint to turn auto-sync ON or OFF.
        Expects JSON: { "enabled": true } or { "enabled": false }
        """
        account = self.get_object()
        enable_sync = request.data.get('enabled')
        
        if enable_sync is None:
            return Response(
                {"error": "Missing 'enabled' field. Send { 'enabled': true } or { 'enabled': false }"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        account.auto_sync_enabled = bool(enable_sync)
        account.updated_by = request.user
        account.save()
        
        state_text = "activated" if account.auto_sync_enabled else "deactivated"
        return Response({
            "success": True, 
            "message": f"Auto-sync {state_text} for {account.account_name}",
            "auto_sync_enabled": account.auto_sync_enabled
        })

    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user, is_deleted=False).order_by('account_name')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

class ClassificationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = ClassificationRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return ClassificationRule.objects.filter(user=self.request.user, is_deleted=False).order_by('priority', 'keyword')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        
    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
        
class EmailModuleSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        settings, created = EmailModuleSettings.objects.get_or_create(
            user=request.user,
            defaults={'created_by': request.user, 'updated_by': request.user}
        )
        serializer = EmailModuleSettingsSerializer(settings)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        settings = get_object_or_404(EmailModuleSettings, user=request.user)
        serializer = EmailModuleSettingsSerializer(settings, data=request.data)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        settings = get_object_or_404(EmailModuleSettings, user=request.user)
        serializer = EmailModuleSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TestConnectionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        account = get_object_or_404(EmailAccount, pk=pk, user=request.user, is_deleted=False)
        test_results = test_account_connection(account)
        account.connection_status = test_results['success']
        account.last_sync_at = timezone.now()
        if not test_results['success']:
            error_log = f"IMAP: {test_results.get('imap_status')} | SMTP: {test_results.get('smtp_status')}"
            account.last_sync_log = error_log
        else:
            account.last_sync_log = "Connection successful."
        account.updated_by = request.user
        account.save()
        return Response(test_results, status=status.HTTP_200_OK)
    
class ProviderDefaultsAPIView(APIView):
    """
    Returns the default IMAP/SMTP settings for supported providers (Gmail, Outlook, etc.).
    Used by the frontend to auto-fill the 'Add Account' form.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Return the dictionary defined in utils.py
        return Response(PROVIDER_DEFAULTS)

class GlobalTestConnectionAPIView(APIView):
    """
    Tests the connection for the FIRST active email account found in the DB.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        account = EmailAccount.objects.filter(user=request.user, is_deleted=False).first()
        
        if not account:
            return Response(
                {"success": False, "error": "No saved email accounts found to test."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Use the same test logic as the other button
        test_results = test_account_connection(account)

        # 4. Save the result to the Global Settings (for the Green/Red Badge)
        settings, _ = EmailModuleSettings.objects.get_or_create(user=request.user)
        settings.imap_connection_status = test_results['success']
        settings.save()

        # 5. Save the result to the Account itself
        account.connection_status = test_results['success']
        account.last_sync_at = timezone.now()
        account.save()

        return Response(test_results)
class ManualSyncAPIView(APIView):
    """
    Manually triggers the sync for a specific account.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        account = get_object_or_404(EmailAccount, pk=pk, user=request.user)
        
        service = EmailSyncService()
        result = service.sync_account(account.id)
        
        return Response(result)