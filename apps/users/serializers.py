# serializers.py
from rest_framework import serializers
from .models import User, Role


# serializers.py
class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""
    permissions = serializers.ListField(source='permission_list', read_only=True)
    default_permissions = serializers.ListField(read_only=True)
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'display_name', 'description', 'permissions','is_system','default_permissions']
    def validate_permissions(self, value):
        """Ensure permissions are sent as a list of strings"""
        if isinstance(value, dict):
            return list(value.keys())
        if not isinstance(value, list):
            raise serializers.ValidationError("Permissions must be a list of strings.")
        return value
class UserListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for the User Management Table.
    Groups data to match specific table columns.
    """
    user = serializers.SerializerMethodField()
    role= serializers.SerializerMethodField()
    permissions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 
            'user',   
            'phone',    
            'role',       
            'department',         
            'status',             
            'permissions_count',  
            'created_at'
        ]

    def get_user(self, obj):
        """Bundles user info for the first column"""
        return {
            "full_name": obj.get_full_name(),
            "email": obj.email,
        }

    def get_role(self, obj):
        """
        Returns ID for he dropdown value and Name for display.
        Handles users with no role (None).
        """
        if obj.role:
            return {
                "id": obj.role.id,          
                "name": obj.role.name,      
                "display_name": obj.role.display_name
            }
        return None  

    def get_permissions_count(self, obj):
        """Safely calculate number of permissions"""
        if obj.role and obj.role.permissions:
            return len(obj.role.permissions)
        return 0
class UserSerializer(serializers.ModelSerializer):
    """Full serializer for User model"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_details = RoleSerializer(source='role', read_only=True)
    assigned_customers_count = serializers.SerializerMethodField()
    send_welcome_email = serializers.BooleanField(write_only=True, required=False, default=False)
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'department', 'job_title', 'employee_id',
            'role', 'role_name', 'role_details', 'avatar', 'bio',
            'timezone', 'language', 'status','force_password_change',
             'send_welcome_email', 'email_notifications',
            'sms_notifications', 'theme_preference', 'last_login',
            'date_joined', 'created_at', 'updated_at',
            'assigned_customers_count',
            
        ]
        read_only_fields = [
            'id', 'last_login', 'date_joined', 'created_at', 'updated_at'
        ]
    def create(self, validated_data):
        """
        Create User with dynamic password generation and email sending.
        """
        # 1. Extract non-model fields
        send_email = validated_data.pop('send_welcome_email', False)
        
        # 2. Dynamic Password Logic
        # If admin didn't provide a password, generate a random secure one
        if 'password' not in validated_data or not validated_data['password']:
            raw_password = BaseUserManager().make_random_password()
            validated_data['password'] = raw_password
        else:
            raw_password = validated_data['password']

        # 3. Create the user securely (hashing the password)
        # We must use create_user() instead of standard create() to ensure hashing
        user = User.objects.create_user(**validated_data)
        
        # 4. Send Real Email if requested
        if send_email:
            self._send_welcome_email(user, raw_password)
            
        return user

    def _send_welcome_email(self, user, raw_password):
        """
        Sends an actual email using Django's SMTP settings.
        """
        subject = f'Welcome to Intelipro - Your Account Details'
        
        # Dynamic Email Body
        message = f"""
        Hello {user.first_name},

        Welcome to the Intelipro Insurance Policy Renewal System.
        Your account has been successfully created by the administrator.

        Here are your temporary login credentials:
        
        ------------------------------------------
        Email:    {user.email}
        Password: {raw_password}
        ------------------------------------------

        Security Note: 
        {'You are required to change your password upon first login.' if user.force_password_change else 'We recommend changing your password after logging in.'}

        Login here: {settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'http://localhost:3000'}

        Best Regards,
        Intelipro Admin Team
        """
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            # Log the error but don't crash the user creation
            print(f"❌ Failed to send welcome email: {str(e)}")
    
    def get_assigned_customers_count(self, obj):
        """Get count of assigned customers"""
        return obj.assigned_customers.count()


class AgentSelectionSerializer(serializers.ModelSerializer):
    """Simplified serializer for agent selection dropdowns"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    workload = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'role_name', 
            'department', 'status', 'workload'
        ]
    
    def get_workload(self, obj):
        """Get current workload count"""
        return obj.assigned_customers.filter(status='active').count()
