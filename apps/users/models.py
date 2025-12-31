"""
User models for the Intelipro Insurance Policy Renewal System.
Implements custom User model with role-based access control (RBAC).
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
import uuid


class UserManager(BaseUserManager):
    """Custom user manager for the User model"""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user"""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class Role(models.Model):
    """Role model for RBAC system"""
    
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=dict, help_text="Permission mappings for this role")
    is_system = models.BooleanField(default=False, help_text="System roles cannot be deleted")
    default_permissions = models.JSONField(default=dict, blank=True, help_text="Factory default permissions for reset")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_role'
        ordering = ['name']
        
    def __str__(self):
        return self.display_name
    
    @property
    def permission_list(self):
        """Return list of permissions for this role"""
        if isinstance(self.permissions, list):
            return self.permissions
        elif isinstance(self.permissions, dict):
            return list(self.permissions.keys())
        else:
            return []
    
    def has_permission(self, permission):
        """Check if role has specific permission"""
        if isinstance(self.permissions, list):
            return permission in self.permissions
        elif isinstance(self.permissions, dict):
            return self.permissions.get(permission, False)
        else:
            return False


class User(AbstractUser):
    """Custom User model for the application"""
    
    # Remove username field and use email as the unique identifier
    username = None
    email = models.EmailField(unique=True, db_index=True)
    
    # Additional user fields
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')]
    )
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    employee_id = models.CharField(max_length=50, blank=True, unique=True, null=True)
    
    # Role-based access control
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    
    # Profile information
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    # Account status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending Activation'),
    ]

    DEPARTMENT_CHOICES = [
        ('claims_processing', 'Claims Processing'),
        ('underwriting', 'Underwriting'),
        ('customer_service', 'Customer Service'),
        ('sales_marketing', 'Sales & Marketing'),
        ('it', 'Information Technology'),
        ('finance_accounting', 'Finance & Accounting'),
        ('legal_compliance', 'Legal & Compliance'),
        ('management', 'Management'),
        ('other', 'Other'),
    ]
    department = models.CharField(
        max_length=100, 
        choices=DEPARTMENT_CHOICES, 
        blank=True,
        default='other'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Security settings
    force_password_change = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    # Multi-factor authentication
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=255, blank=True)
    backup_tokens = models.JSONField(default=list, blank=True)
    
    # Login tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    
    # Preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    theme_preference = models.CharField(
        max_length=10,
        choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')],
        default='light'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        ordering = ['first_name', 'last_name']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['role']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        """Return the user's full name"""
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def initials(self):
        """Return user's initials"""
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()
    
    def has_permission(self, permission):
        """Check if user has specific permission through their role"""
        if self.is_superuser:
            return True
        if not self.role:
            return False
        return self.role.has_permission(permission)
    
    def get_permissions(self):
        """Get all permissions for this user"""
        if self.is_superuser:
            return ['*']  # Superuser has all permissions
        if not self.role:
            # Try to assign default role if none exists
            self.assign_default_role()
            if self.role:
                return self.role.permission_list
            return []
        return self.role.permission_list
    
    def assign_default_role(self):
        """Assign default role if user doesn't have one"""
        if not self.role:
            try:
                # Try to get agent role first (most common for regular users)
                default_role = Role.objects.get(name='agent')
                self.role = default_role
                self.save(update_fields=['role'])
                return True
            except Role.DoesNotExist:
                # If agent role doesn't exist, try any available role
                try:
                    default_role = Role.objects.first()
                    if default_role:
                        self.role = default_role
                        self.save(update_fields=['role'])
                        return True
                except Exception:
                    pass
        return False
    
    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.locked_until:
            return timezone.now() < self.locked_until
        return False
    
    def unlock_account(self):
        """Unlock the user account"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until'])
    
    def record_login_attempt(self, success=True, ip_address=None):
        """Record login attempt"""
        if success:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.last_login_ip = ip_address
            self.last_activity = timezone.now()
            self.login_count += 1
        else:
            self.failed_login_attempts += 1
            # Lock account after 5 failed attempts for 30 minutes
            if self.failed_login_attempts >= 5:
                self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        
        self.save(update_fields=[
            'failed_login_attempts', 'locked_until', 'last_login_ip',
            'last_activity', 'login_count'
        ])


class UserSession(models.Model):
    """Track active user sessions"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.ip_address}"
    
    def is_expired(self):
        """Check if session is expired"""
        return timezone.now() > self.expires_at
    
    def extend_session(self, minutes=60):
        """Extend session expiry time"""
        self.expires_at = timezone.now() + timezone.timedelta(minutes=minutes)
        self.last_activity = timezone.now()
        self.save(update_fields=['expires_at', 'last_activity'])


class UserPreference(models.Model):
    """Store user-specific preferences and settings"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    dashboard_config = models.JSONField(default=dict, blank=True)
    notification_settings = models.JSONField(default=dict, blank=True)
    ui_settings = models.JSONField(default=dict, blank=True)
    filter_presets = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} preferences"


class PasswordResetToken(models.Model):
    """Password reset tokens"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Password reset for {self.user.email}"
    
    def is_expired(self):
        """Check if token is expired"""
        return timezone.now() > self.expires_at
    
    def mark_as_used(self, ip_address=None):
        """Mark token as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.ip_address = ip_address
        self.save(update_fields=['is_used', 'used_at', 'ip_address']) 