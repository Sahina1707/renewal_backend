from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.timesince import timesince

User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Formatted specifically for the 'My Profile' UI layout.
    """
    # Section 1: Header Card (Left Side)
    my_profile = serializers.SerializerMethodField()
    
    # Section 2: Profile Information (Right Side - Top)
    profile_information = serializers.SerializerMethodField()
    
    # Section 3: Account Security (Right Side - Bottom)
    account_security = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['my_profile', 'profile_information', 'account_security']

    def get_my_profile(self, obj):
        return {
            "avatar": obj.avatar.url if obj.avatar else None,
            "initials": obj.initials,  
            "full_name": obj.get_full_name(),
            "role_label": obj.role.display_name if obj.role else "No Role",
            "department_badge": obj.get_department_display() if obj.department else "General",
            "member_since": obj.date_joined.strftime("%B %d, %Y"), 
            "last_login": obj.last_login.strftime("%B %d, %Y") if obj.last_login else "Never"
        }

    def get_profile_information(self, obj):
        return {
            "full_name": obj.get_full_name(),
            "email": obj.email,
            "phone": obj.phone if obj.phone else "Not provided",
            "job_title": obj.job_title
        }

    def get_account_security(self, obj):
        if obj.password_changed_at:
            time_diff = timesince(obj.password_changed_at).split(',')[0]
            last_changed_text = f"Last changed {time_diff} ago"
        else:
            last_changed_text = "Not changed recently"

        return {
            "password_status": "Active",
            "last_changed_label": last_changed_text
        }

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_new_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({"new_password": "New passwords must match."})
        return data
class UpdateUserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for SAVING profile updates.
    It accepts a flat JSON structure (easier for React forms).
    """
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 
            'phone', 'job_title', 'bio', 
            'avatar', 'theme_preference',
            'email_notifications', 'sms_notifications'
        ]