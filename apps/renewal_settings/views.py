from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import RenewalSettings, QuickMessageSettings
from .serializers import RenewalSettingsSerializer, QuickMessageSettingsSerializer, PROVIDER_CAPABILITIES
from apps.call_provider.models import CallProviderConfig 
from apps.call_provider.serializers import CallProviderConfigSerializer
from apps.call_provider.services import CallProviderService
from apps.sms_provider.services import SmsService
from apps.whatsapp_provider.services import WhatsAppService

# --- VIEW 1: General Settings (Get Active & Update Globals) ---
class RenewalSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Fetch the currently ACTIVE profile. 
        If no provider is active, try to return the first one found or empty.
        """
        # Try to find the row where integration is TRUE
        settings = RenewalSettings.objects.filter(enable_call_integration=True).first()
        
        # If no one is active, just pick the first available profile, or create a dummy one if empty
        if not settings:
            settings = RenewalSettings.objects.first()

        if not settings:
             return Response({"message": "No settings configured yet."}, status=200)

        serializer = RenewalSettingsSerializer(settings)
        
        # Available Providers list for the dropdown
        providers = CallProviderConfig.objects.filter(is_active=True, is_deleted=False).values('id', 'name', 'provider_type')
        
        data = serializer.data
        data['available_providers'] = list(providers)
        # 3. Add Capabilities Map (Frontend needs this for validation rules)
        data['provider_capabilities'] = PROVIDER_CAPABILITIES
        
        # 4. Inject Quick Message Settings (USER REQUEST: Combine into one response)
        qm_settings = QuickMessageSettings.objects.first()
        if qm_settings:
            data['quick_message_settings'] = QuickMessageSettingsSerializer(qm_settings).data
        else:
            data['quick_message_settings'] = None

        return Response(data)

    def patch(self, request):
        """
        Updates GLOBAL settings (Auto Refresh, Edit Button, Master Switch) without needing a Provider ID.
        This updates the columns for EVERY row in the database at once.
        """
        # 1. Define Global Fields
        # We include 'enable_call_integration' here so it acts as a Master Switch for the whole module
        global_fields = [
            'auto_refresh_enabled', 
            'show_edit_case_button', 
            'enforce_provider_limits', 
            'enable_call_integration',
            'default_renewal_period', # Added
            'auto_assign_cases' # Added
        ]
        
        # 2. Filter the request data
        updates = {}
        for field in global_fields:
            if field in request.data:
                updates[field] = request.data[field]
        
        # 3. Update the Database (ALL ROWS)
        if updates:
            # This turns the feature ON/OFF or updates settings for everyone at once
            RenewalSettings.objects.all().update(**updates)
            
            return Response({
                "message": "Global settings updated successfully.",
                "updated_fields": updates
            }, status=200)

        return Response({"message": "No global settings provided to update."}, status=400)


# --- VIEW 2: Specific Provider Detail & Update Logic ---
class RenewalSettingsDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_or_create_profile(self, provider_id):
        try:
            target_provider = CallProviderConfig.objects.get(id=provider_id)
            # Find the existing profile OR create a new one for this provider
            obj, created = RenewalSettings.objects.get_or_create(
                active_provider=target_provider,
                defaults={
                    'default_call_duration': 30,
                    'enable_call_recording': True,
                    'auto_refresh_enabled': True, # Default for new rows
                    'enable_call_integration': False
                }
            )
            return obj, target_provider
        except CallProviderConfig.DoesNotExist:
            return None, None

    def get(self, request, provider_id):
        settings, target_provider = self.get_or_create_profile(provider_id)
        
        if not settings:
            return Response({"error": "Provider ID not found"}, status=404)

        serializer = RenewalSettingsSerializer(settings)
        data = serializer.data
        
        # Inject details for the Frontend
        data['available_providers'] = [{'id': target_provider.id, 'name': target_provider.name, 'provider_type': target_provider.provider_type}]
        data['provider_capabilities'] = PROVIDER_CAPABILITIES
        
        return Response(data)

    def patch(self, request, provider_id):
        """
        Updates Global fields (Synced), Specific fields (Unique), and Credentials (Provider Table).
        """
        # 1. Get the Profile Row
        settings, target_provider = self.get_or_create_profile(provider_id)
        if not settings:
            return Response({"error": "Provider ID not found"}, status=404)

        # 2. SEPARATE FIELDS (Global vs Specific)
        # 2. SEPARATE FIELDS (Global vs Specific)
        # Added 'default_renewal_period', 'auto_assign_cases', 'enable_call_integration' as global fields
        global_fields = [
            'auto_refresh_enabled', 
            'show_edit_case_button', 
            'enforce_provider_limits',
            'default_renewal_period',
            'auto_assign_cases',
            'enable_call_integration'
        ]
        
        # --- LOGIC A: SYNC GLOBAL FIELDS ---
        # If user updates 'auto_refresh' OR 'default_renewal_period' etc., we must update it in EVERY row.
        global_updates = {}
        for field in global_fields:
            if field in request.data:
                global_updates[field] = request.data[field]
        
        if global_updates:
            # Update all rows at once
            RenewalSettings.objects.all().update(**global_updates)
            # Also update current instance so serializer returns fresh data
            for k, v in global_updates.items():
                setattr(settings, k, v)

        # --- LOGIC B: UPDATE SPECIFIC FIELDS ---
        # Update using serializer (handles validation like max duration, etc.)
        # global fields in 'data' will be ignored by serializer (if read-only) or overwritten by our manual sync above.
        serializer = RenewalSettingsSerializer(settings, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        settings = serializer.save()

        # --- LOGIC C: INDEPENDENT TOGGLE ---
        # Removed distinct handling for 'enable_call_integration' since it is now Global (handled in Logic A).
        # We NO LONGER treat it as independent.

        # --- LOGIC D: SAVE CREDENTIALS TO PROVIDER TABLE ---
        # Map input fields to Provider model fields
        provider_data = {}
        fields_map = {
            'twilio': ['twilio_account_sid', 'twilio_auth_token', 'twilio_from_number'],
            'exotel': ['exotel_api_key', 'exotel_api_token', 'exotel_subdomain', 'exotel_account_sid', 'exotel_caller_id'],
            'ubona': ['ubona_api_key', 'ubona_api_url', 'ubona_account_sid', 'ubona_caller_id']
        }
        
        p_type = target_provider.provider_type
        for field in fields_map.get(p_type, []):
            if field in request.data:
                provider_data[field] = request.data[field]

        # Encrypt sensitive keys
        if provider_data:
            service = CallProviderService()
            for field in ['twilio_auth_token', 'exotel_api_key', 'exotel_api_token', 'ubona_api_key']:
                if field in provider_data and provider_data[field]:
                    provider_data[field] = service._encrypt_credential(provider_data[field])

            # Update the Provider Object
            for key, value in provider_data.items():
                setattr(target_provider, key, value)
            
            # If concurrent limit changed, sync it to provider limit too
            if 'max_concurrent_calls' in request.data:
                target_provider.rate_limit_per_minute = request.data['max_concurrent_calls']

            target_provider.updated_by = request.user
            target_provider.save()

        # --- RETURN RESPONSE ---
        response_data = RenewalSettingsSerializer(settings).data
        return Response(response_data, status=200)


# --- VIEW 3: Quick Message Settings (SMS & WhatsApp) ---
class QuickMessageSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Fetch the configuration for Quick Message Settings.
        Logic: Return the LATEST active configuration.
        """
        from .models import QuickMessageSettings
        
        # 1. Fetch Latest Active
        settings_obj = QuickMessageSettings.objects.filter(is_active_configuration=True).last()
        
        # Fallback: If no settings exist at all, return empty or defaults
        if not settings_obj:
            # Create a default initial row if table is empty
            if not QuickMessageSettings.objects.exists():
                settings_obj = QuickMessageSettings.objects.create(is_active_configuration=True)
            else:
                 # If we have rows but none active (rare), just pick the absolute last one
                 settings_obj = QuickMessageSettings.objects.last()

        # 2. Serialize user-facing settings
        serializer = QuickMessageSettingsSerializer(settings_obj)
        data = serializer.data

        # 3. Add Inventory Lists (for Dropdowns)
        from apps.sms_provider.models import SmsProvider
        from apps.whatsapp_provider.models import WhatsAppProvider
        
        data['available_sms_providers'] = list(
            SmsProvider.objects.filter(is_active=True, is_deleted=False).values('id', 'name', 'provider_type')
        )
        data['available_whatsapp_providers'] = list(
            WhatsAppProvider.objects.filter(is_active=True, is_deleted=False).values('id', 'name', 'provider_type', 'account_id')
        )

        return Response(data)

    def patch(self, request):
        """
        Update Quick Message Settings with HISTORY TRACKING.
        Logic:
           1. Find current active row.
           2. 'Clone' its data with the new updates from request.
           3. Archive current row (is_active=False).
           4. Create NEW row (is_active=True) with merged data.
        """
        from .models import QuickMessageSettings
        from .serializers import QuickMessageSettingsSerializer
        from django.forms.models import model_to_dict
        
        # 1. Get Current Active Settings (The "Old" one)
        old_obj = QuickMessageSettings.objects.filter(is_active_configuration=True).last()
        
        # 2. Prepare Data for New Row (Cloning)
        new_data = {}
        if old_obj:
            # Start with a copy of the old data
            # model_to_dict excludes many-to-many and fields we might not want, but handling FKs is key.
            # We manually extract the fields we care about to be safe and explicit.
            new_data = {
                'enable_quick_message_integration': old_obj.enable_quick_message_integration,
                'active_sms_provider': old_obj.active_sms_provider.id if old_obj.active_sms_provider else None,
                'active_whatsapp_provider': old_obj.active_whatsapp_provider.id if old_obj.active_whatsapp_provider else None,
                'enable_delivery_reports': old_obj.enable_delivery_reports,
                'enable_message_analytics': old_obj.enable_message_analytics,
                'rate_limit_per_minute': old_obj.rate_limit_per_minute,
                'daily_message_limit': old_obj.daily_message_limit,
                'policy_renewal_reminder_template': old_obj.policy_renewal_reminder_template,
                'claim_status_update_template': old_obj.claim_status_update_template,
                'payment_confirmation_template': old_obj.payment_confirmation_template,
            }
        
        # 3. Merge with User Updates
        # request.data values override the old_data
        new_data.update(request.data)
        
        # Force the new row to be Active
        new_data['is_active_configuration'] = True

        # 4. Save New Row
        serializer = QuickMessageSettingsSerializer(data=new_data)
        if serializer.is_valid():
            new_settings_obj = serializer.save()
            
            # 5. Archive the Old Row
            if old_obj and old_obj.id != new_settings_obj.id:
                old_obj.is_active_configuration = False
                old_obj.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # 6. PROXY LOGIC - WHATSAPP (Same as before, runs on the NEW active provider)
        wa_provider = new_settings_obj.active_whatsapp_provider
        if wa_provider:
             wa_updates = {}
             # Sync Limits
             if 'rate_limit_per_minute' in request.data: wa_updates['rate_limit_per_minute'] = request.data['rate_limit_per_minute']
             if 'daily_message_limit' in request.data: wa_updates['daily_limit'] = request.data['daily_message_limit']

             if 'wa_access_token' in request.data: wa_updates['access_token'] = request.data['wa_access_token']
             if 'wa_phone_number_id' in request.data: wa_updates['phone_number_id'] = request.data['wa_phone_number_id']
             if 'wa_business_account_id' in request.data: wa_updates['account_id'] = request.data['wa_business_account_id']
             
             if wa_updates:
                 for k, v in wa_updates.items():
                     setattr(wa_provider, k, v)
                 wa_provider.save()

        # 7. PROXY LOGIC - SMS
        sms_provider = new_settings_obj.active_sms_provider
        if sms_provider:
            # Sync Limits
            sms_updates = {}
            if 'rate_limit_per_minute' in request.data: sms_updates['rate_limit_per_minute'] = request.data['rate_limit_per_minute']
            if 'daily_message_limit' in request.data: sms_updates['daily_limit'] = request.data['daily_message_limit']
            
            if sms_updates:
                for k, v in sms_updates.items():
                    setattr(sms_provider, k, v)
                # save immediately so limits are applied even if credentials aren't changing
                sms_provider.save()

            credentials = sms_provider.credentials or {}
            p_type = sms_provider.provider_type
            updates_made = False
            
            if p_type == 'twilio':
                if 'sms_sender_id' in request.data: credentials['from_number'] = request.data['sms_sender_id']; updates_made=True
                if 'sms_auth_token' in request.data: credentials['auth_token'] = request.data['sms_auth_token']; updates_made=True
                if 'sms_api_key' in request.data: credentials['account_sid'] = request.data['sms_api_key']; updates_made=True
            elif p_type in ['msg91', 'textlocal']:
                if 'sms_api_key' in request.data: credentials['api_key'] = request.data['sms_api_key']; updates_made=True
                if 'sms_sender_id' in request.data: credentials['sender_id'] = request.data['sms_sender_id']; updates_made=True

            if updates_made:
                sms_provider.credentials = credentials
                sms_provider.save()

        return Response(serializer.data, status=200)


# =========================================================
#  INTEGRATION TESTING VIEWS
# =========================================================

class TestCallIntegrationView(APIView):
    """
    Tests the connection of the ACTIVE Call Provider linked in RenewalSettings.
    """
    def post(self, request):
        try:
            settings_obj = RenewalSettings.objects.first()
            if not settings_obj:
                return Response({"status": "error", "message": "Renewal Settings not found."}, status=404)
            
            provider = settings_obj.active_provider
            if not provider:
                return Response({"status": "error", "message": "No Active Call Provider configured."}, status=400)

            # Use the service factory to check health
            factory = CallProviderService()
            result = factory.check_provider_health(provider, user=request.user)
            
            # --- PERSIST STATUS (USER REQUEST) ---
            # If "Connected", mark ALL rows as connected. If failed, mark ALL as disconnected.
            is_connected = result.get('success', False)
            RenewalSettings.objects.all().update(is_call_integration_testing=is_connected)
            
            return Response({
                "provider": provider.name,
                "type": provider.provider_type,
                "result": result,
                "db_updated": True,
                "is_connected_stored": is_connected
            })
            
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)


class TestSmsIntegrationView(APIView):
    """
    Tests the connection of the ACTIVE SMS Provider.
    Updates the 'is_sms_integration_testing' column in RenewalSettings (for ALL rows).
    """
    def post(self, request):
        try:
            settings_obj = QuickMessageSettings.objects.first()
            if not settings_obj:
                return Response({"status": "error", "message": "Quick Message Settings not configured."}, status=404)
            
            provider = settings_obj.active_sms_provider
            if not provider:
                return Response({"status": "error", "message": "No Active SMS Provider configured in Quick Message Settings."}, status=400)

            # Instantiate service and check health
            service = SmsService().get_service_instance(provider.id)
            health = service.health_check()
            
            # --- PERSIST STATUS ---
            # 'status' usually returns 'connected', 'authenticated', etc.
            # We assume anything OTHER than 'unhealthy' or 'error' is good, or check specifically for 'connected'.
            is_connected = health.get('status') == 'connected'
            
            # Update GLOBAL status in RenewalSettings table (for all rows)
            RenewalSettings.objects.all().update(is_sms_integration_testing=is_connected)
            
            return Response({
                "provider": provider.name,
                "type": provider.provider_type,
                "result": health,
                "db_updated": True,
                "is_connected_stored": is_connected
            })
            
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)


class TestWhatsAppIntegrationView(APIView):
    """
    Tests the connection of the ACTIVE WhatsApp Provider.
    Updates the 'is_whatsapp_integration_testing' column in RenewalSettings (for ALL rows).
    """
    def post(self, request):
        try:
            settings_obj = QuickMessageSettings.objects.first()
            if not settings_obj:
                return Response({"status": "error", "message": "Quick Message Settings not configured."}, status=404)
            
            provider = settings_obj.active_whatsapp_provider
            if not provider:
                return Response({"status": "error", "message": "No Active WhatsApp Provider configured in Quick Message Settings."}, status=400)

            # Instantiate service and check health
            service = WhatsAppService().get_service_instance(provider.id)
            health = service.health_check()
            
            # --- PERSIST STATUS ---
            # Check for 'healthy', 'connected', or 'green' depending on provider
            status_val = health.get('status', '').lower()
            is_connected = status_val in ['connected', 'healthy', 'green']
            
            # Update GLOBAL status in RenewalSettings table (for all rows)
            RenewalSettings.objects.all().update(is_whatsapp_integration_testing=is_connected)
            
            return Response({
                "provider": provider.name,
                "type": provider.provider_type,
                "result": health,
                "db_updated": True,
                "is_connected_stored": is_connected
            })
            
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)


class PolicySettingsView(APIView):
    """
    Dedicated endpoint for Policy Renewal Rules (Slider & Auto-Assign).
    URL: /renewal-settings/policy/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Just grab the first available settings object since these are global
        settings = RenewalSettings.objects.first()
        
        data = {
            "default_renewal_period": 30, # Default
            "auto_assign_cases": False    # Default
        }
        
        if settings:
            data['default_renewal_period'] = settings.default_renewal_period
            data['auto_assign_cases'] = settings.auto_assign_cases
            
        return Response(data)

    def patch(self, request):
        """
        Global update for Policy settings (synced across all rows).
        """
        updates = {}
        if 'default_renewal_period' in request.data:
            updates['default_renewal_period'] = request.data['default_renewal_period']
        if 'auto_assign_cases' in request.data:
            updates['auto_assign_cases'] = request.data['auto_assign_cases']
            
        if updates:
            # Sync to ALL rows
            RenewalSettings.objects.all().update(**updates)
            return Response({
                "message": "Policy settings updated successfully.",
                "updated_fields": updates
            })
            
        return Response({"message": "No policy settings provided."}, status=400)


class AutoRefreshSettingsView(APIView):
    """
    Dedicated endpoint for Auto-Refresh & Edit UI Settings.
    URL: /renewal-settings/auto-refresh/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = RenewalSettings.objects.first()
        data = {
            "auto_refresh_enabled": True,    # Default
            "show_edit_case_button": True    # Default
        }
        if settings:
            data['auto_refresh_enabled'] = settings.auto_refresh_enabled
            data['show_edit_case_button'] = settings.show_edit_case_button
            
        return Response(data)

    def patch(self, request):
        updates = {}
        if 'auto_refresh_enabled' in request.data:
            updates['auto_refresh_enabled'] = request.data['auto_refresh_enabled']
        if 'show_edit_case_button' in request.data:
            updates['show_edit_case_button'] = request.data['show_edit_case_button']
            
        if updates:
            RenewalSettings.objects.all().update(**updates)
            return Response({
                "message": "Auto-refresh settings updated successfully.",
                "updated_fields": updates
            })
        return Response({"message": "No settings provided."}, status=400)


class CallIntegrationGlobalView(APIView):
    """
    Dedicated endpoint for Call Integration Master Switch & Limits.
    URL: /renewal-settings/call-integration/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = RenewalSettings.objects.filter(enable_call_integration=True).first()
        if not settings:
             settings = RenewalSettings.objects.first()
             
        data = {
            "enable_call_integration": False,    # Default
            "enforce_provider_limits": True,     # Default
            "default_call_duration": 30,
            "max_concurrent_calls": 10,
            "enable_call_recording": True,
            "enable_call_analytics": False,
            "active_provider_details": None
        }
        
        if settings:
            data['enable_call_integration'] = settings.enable_call_integration
            data['enforce_provider_limits'] = settings.enforce_provider_limits
            data['default_call_duration'] = settings.default_call_duration
            data['max_concurrent_calls'] = settings.max_concurrent_calls
            data['enable_call_recording'] = settings.enable_call_recording
            data['enable_call_analytics'] = settings.enable_call_analytics
            
            if settings.active_provider:
                 data['active_provider'] = settings.active_provider.id
                 data['active_provider_details'] = {
                     "id": settings.active_provider.id,
                     "name": settings.active_provider.name,
                     "provider_type": settings.active_provider.provider_type
                 }
            
        return Response(data)

    def patch(self, request):
        # 1. Separate Global vs Specific Fields
        global_fields = ['enable_call_integration', 'enforce_provider_limits']
        specific_fields = [
            'default_call_duration', 'max_concurrent_calls',
            'enable_call_recording', 'enable_call_analytics'
        ]
        
        global_updates = {}
        specific_updates = {}
        
        for field in global_fields:
            if field in request.data:
                global_updates[field] = request.data[field]
                
        for field in specific_fields:
            if field in request.data:
                specific_updates[field] = request.data[field]

        # 1.5 VALIDATION PRE-CHECK
        # Determine which provider we are operating on to check its rules
        validation_provider_id = None
        if 'active_provider' in request.data:
            validation_provider_id = request.data['active_provider']
        else:
             # Use current default if not switching
             current = CallProviderConfig.objects.filter(is_default=True).first()
             if current:
                 validation_provider_id = current.id
        
        if validation_provider_id:
            # We need an instance to validate against user's specific limits/capabilities
            # We get or create the profile just for validation context
            val_instance = RenewalSettings.objects.filter(active_provider_id=validation_provider_id).first()
            if not val_instance:
                 # If it doesn't exist yet, we can't fully validate or we assume it's created defaults. 
                 # Let's try to get the provider object safely
                 try:
                     prov_obj = CallProviderConfig.objects.get(id=validation_provider_id)
                     val_instance = RenewalSettings(active_provider=prov_obj) # Temporary instance
                 except:
                     pass
            
            if val_instance:
                # Run the Serializer Validation logic (checks Ubona recording, Exotel limits etc)
                # We typically rely on the existing serializer for this
                from .serializers import RenewalSettingsSerializer
                serializer = RenewalSettingsSerializer(instance=val_instance, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)

        # 2. Handle Active Provider Switch (Updates CallProviderConfig)
        target_provider_id = validation_provider_id 
        if 'active_provider' in request.data:
            try:
                target_provider_id = request.data['active_provider']
                # Reset others, set this one as default
                CallProviderConfig.objects.all().update(is_default=False)
                CallProviderConfig.objects.filter(id=target_provider_id).update(is_default=True)
                # Log or handle invalid ID if necessary
                pass
            except Exception:
                # Log or handle invalid ID if necessary
                pass
            
        # 3. Apply Global Updates (To ALL rows)
        if global_updates:
            RenewalSettings.objects.all().update(**global_updates)
            
        # 4. Apply Specific Updates (To CURRENT Active Provider row only)
        if specific_updates and target_provider_id:
            RenewalSettings.objects.filter(active_provider_id=target_provider_id).update(**specific_updates)
            
        return Response({
            "message": "Call integration global settings updated successfully.",
            "global_updates": global_updates,
            "specific_updates": specific_updates,
            "active_provider_updated": 'active_provider' in request.data
        })


class IntegrationSettingsView(APIView):
    """
    Dedicated endpoint for Integration Connection Status.
    URL: /renewal-settings/integration-settings/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = RenewalSettings.objects.first()
        data = {
            "is_call_integration_testing": False,
            "is_sms_integration_testing": False,
            "is_whatsapp_integration_testing": False
        }
        if settings:
            data['is_call_integration_testing'] = settings.is_call_integration_testing
            data['is_sms_integration_testing'] = settings.is_sms_integration_testing
            data['is_whatsapp_integration_testing'] = settings.is_whatsapp_integration_testing
            
        return Response(data)

    def patch(self, request):
        """
        Manually update status flags if needed (though usually done via /test-integration/).
        """
        updates = {}
        fields = ['is_call_integration_testing', 'is_sms_integration_testing', 'is_whatsapp_integration_testing']
        
        for field in fields:
            if field in request.data:
                updates[field] = request.data[field]
            
        if updates:
            RenewalSettings.objects.all().update(**updates)
            return Response({
                "message": "Integration status updated successfully.",
                "updated_fields": updates
            })
        return Response({"message": "No settings provided."}, status=400)