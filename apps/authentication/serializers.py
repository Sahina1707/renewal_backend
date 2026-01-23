
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from apps.users.models import User, Role
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields.pop('username')

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                username=email, 
                password=password
            )

            if not user:
                raise serializers.ValidationError({"email": "Invalid email or password."})

            refresh = RefreshToken.for_user(user)
            return {
                'email': user.email,
                'user_id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': user,  
            }

        raise serializers.ValidationError({"email": "Must include email and password."})


    def get_token(self, user):
        token = super().get_token(user)
        token['user_id'] = user.id
        token['email'] = user.email
        token['full_name'] = user.full_name
        token['role'] = user.role.name if user.role else None
        token['permissions'] = user.get_permissions()
        return token

    def get_client_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')


class UserRegistrationSerializer(serializers.ModelSerializer):    
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    role_name = serializers.CharField(write_only=True, required=False)
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone', 'department', 
            'job_title', 'employee_id', 'password', 'password_confirm', 'role_name'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError("User with this email already exists.")
        
        role_name = attrs.pop('role_name', None)
        if role_name:
            try:
                role = Role.objects.get(name=role_name, is_active=True)
                attrs['role'] = role
            except Role.DoesNotExist:
                raise serializers.ValidationError(f"Role '{role_name}' not found.")
        else:
            try:
                default_role = Role.objects.get(name='agent')
                attrs['role'] = default_role
            except Role.DoesNotExist:
                try:
                    default_role = Role.objects.first()
                    if default_role:
                        attrs['role'] = default_role
                except Exception:
                    pass
        
        attrs.pop('password_confirm')
        return attrs
    
    def create(self, validated_data):
        """Create new user"""
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate password change data"""
        user = self.context['request'].user
        
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError("Current password is incorrect.")
        
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords don't match.")
        
        return attrs
    
    def save(self):
        """Change user password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.password_changed_at = timezone.now()
        user.force_password_change = False
        user.save(update_fields=['password', 'password_changed_at', 'force_password_change'])
        return user
class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate email exists"""
        try:
            User.objects.get(email=value, is_active=True)
        except User.DoesNotExist:
            pass
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):    
    token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate password reset data"""
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):    
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_display_name = serializers.CharField(source='role.display_name', read_only=True)
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone', 'department',
            'job_title', 'employee_id', 'avatar', 'bio', 'timezone', 'language',
            'status', 'role_name', 'role_display_name', 'permissions',
            'email_notifications', 'sms_notifications', 'theme_preference',
            'last_login', 'date_joined', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'last_login', 'date_joined', 'created_at', 'updated_at']
    
    def get_permissions(self, obj):
        """Get user permissions"""
        return obj.get_permissions()

class LoginResponseSerializer(serializers.Serializer):    
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserProfileSerializer()
    class Meta:
        fields = ['access', 'refresh', 'user']