from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class EmailProviderConfig(models.Model):
    """Configuration for email providers (SendGrid, AWS SES, SMTP)"""
    
    PROVIDER_CHOICES = [
        ('sendgrid', 'SendGrid'),
        ('aws_ses', 'AWS SES'),
        ('mailgun', 'Mailgun'),
        ('smtp', 'Custom SMTP'),
    ]
    
    PRIORITY_CHOICES = [
        (1, 'Primary'),
        (2, 'Secondary'),
        (3, 'Tertiary'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Friendly name for this provider")
    provider_type = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    
    # Provider-specific credentials (encrypted)
    api_key = models.TextField(blank=True, null=True, help_text="API key (encrypted)")
    api_secret = models.TextField(blank=True, null=True, help_text="API secret (encrypted)")
    access_key_id = models.CharField(max_length=255, blank=True, null=True, help_text="AWS Access Key ID (encrypted)")
    secret_access_key = models.CharField(max_length=255, blank=True, null=True, help_text="AWS Secret Access Key (encrypted)")
    
    # AWS SES specific fields
    aws_region = models.CharField(max_length=50, blank=True, null=True, help_text="AWS region for SES")
    
    # Mailgun specific fields
    domain = models.CharField(max_length=255, blank=True, null=True, help_text="Mailgun domain")
    
    # SMTP specific fields
    smtp_host = models.CharField(max_length=255, blank=True, null=True, help_text="SMTP server host")
    smtp_port = models.PositiveIntegerField(blank=True, null=True, help_text="SMTP server port")
    smtp_username = models.CharField(max_length=255, blank=True, null=True, help_text="SMTP username (encrypted)")
    smtp_password = models.CharField(max_length=255, blank=True, null=True, help_text="SMTP password (encrypted)")
    smtp_use_tls = models.BooleanField(default=False, help_text="Use TLS for SMTP connection")
    smtp_use_ssl = models.BooleanField(default=False, help_text="Use SSL for SMTP connection")

    # Email settings
    from_email = models.EmailField(help_text="Default from email address")
    from_name = models.CharField(max_length=100, blank=True, null=True)
    reply_to = models.EmailField(blank=True, null=True)
    
    # Rate limiting
    daily_limit = models.PositiveIntegerField(default=1000, help_text="Daily email limit")
    monthly_limit = models.PositiveIntegerField(default=30000, help_text="Monthly email limit")
    rate_limit_per_minute = models.PositiveIntegerField(default=10, help_text="Rate limit per minute")
    
    # Configuration
    priority = models.PositiveIntegerField(choices=PRIORITY_CHOICES, default=1)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Health monitoring
    last_health_check = models.DateTimeField(blank=True, null=True)
    health_status = models.CharField(max_length=20, default='unknown', choices=[
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
        ('unknown', 'Unknown'),
    ])
    
    # Usage tracking
    emails_sent_today = models.PositiveIntegerField(default=0)
    emails_sent_this_month = models.PositiveIntegerField(default=0)
    last_reset_daily = models.DateField(default=timezone.now)
    last_reset_monthly = models.DateField(default=timezone.now)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_providers')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_email_providers')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_email_providers')
    
    class Meta:
        db_table = 'email_provider_configs'
        ordering = ['priority', 'name']
        verbose_name = 'Email Provider Configuration'
        verbose_name_plural = 'Email Provider Configurations'
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"
    
    def update_health_status(self, is_healthy: bool, error_message: str = None, response_time: float = None):
        """Update the health status of the provider"""
        self.last_health_check = timezone.now()
        self.health_status = 'healthy' if is_healthy else 'unhealthy'
        self.save(update_fields=['last_health_check', 'health_status'])
        
        # Log the health check
        EmailProviderHealthLog.objects.create(
            provider=self,
            is_healthy=is_healthy,
            error_message=error_message or '',
            response_time=response_time or 0.0, 
            status='active',
            test_type='health_check'
        )
    
    def can_send_email(self) -> bool:
        """Check if provider can send email based on limits and health"""
        if not self.is_active or self.health_status != 'healthy':
            return False
        
        # Check daily limit
        if self.emails_sent_today >= self.daily_limit:
            return False
        
        # Check monthly limit
        if self.emails_sent_this_month >= self.monthly_limit:
            return False
        
        return True
    
    def increment_usage(self, count: int = 1):
        """Increment email usage counters"""
        self.emails_sent_today += count
        self.emails_sent_this_month += count
        self.save(update_fields=['emails_sent_today', 'emails_sent_this_month'])
    
    def reset_daily_usage(self):
        """Reset daily usage counter (called by scheduled task)"""
        self.emails_sent_today = 0
        self.last_reset_daily = timezone.now().date()
        self.save(update_fields=['emails_sent_today', 'last_reset_daily'])
    
    def reset_monthly_usage(self):
        """Reset monthly usage counter (called by scheduled task)"""
        self.emails_sent_this_month = 0
        self.save(update_fields=['emails_sent_this_month'])
    
    def soft_delete(self):
        """Soft delete the provider"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active'])


class EmailProviderHealthLog(models.Model):
    """Log of health check results for email providers"""
    
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(EmailProviderConfig, on_delete=models.CASCADE, related_name='health_logs')
    is_healthy = models.BooleanField()
    error_message = models.TextField(blank=True, null=True)
    response_time = models.FloatField(default=0.0, help_text="Response time in seconds")
    checked_at = models.DateTimeField(auto_now_add=True)
    
    # Additional fields that exist in database
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default='active')
    test_type = models.CharField(max_length=50, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_health_logs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_health_logs')
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_health_logs')
    
    class Meta:
        db_table = 'email_provider_health_logs'
        ordering = ['-checked_at']
        verbose_name = 'Email Provider Health Log'
        verbose_name_plural = 'Email Provider Health Logs'
    
    def __str__(self):
        status = "Healthy" if self.is_healthy else "Unhealthy"
        return f"{self.provider.name} - {status} ({self.checked_at})"


class EmailProviderUsageLog(models.Model):
    """Log of email sending usage for providers"""
    
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(EmailProviderConfig, on_delete=models.CASCADE, related_name='usage_logs')
    emails_sent = models.PositiveIntegerField()
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    total_response_time = models.FloatField(default=0.0, help_text="Total response time in seconds")
    logged_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_provider_usage_logs'
        ordering = ['-logged_at']
        verbose_name = 'Email Provider Usage Log'
        verbose_name_plural = 'Email Provider Usage Logs'
    
    def __str__(self):
        return f"{self.provider.name} - {self.emails_sent} emails ({self.logged_at})"


class EmailProviderTestResult(models.Model):
    """Test results for email provider configurations"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    provider = models.ForeignKey(EmailProviderConfig, on_delete=models.CASCADE, related_name='test_results')
    test_email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    response_time = models.FloatField(blank=True, null=True, help_text="Response time in seconds")
    tested_at = models.DateTimeField(auto_now_add=True)
    tested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'email_provider_test_results'
        ordering = ['-tested_at']
        verbose_name = 'Email Provider Test Result'
        verbose_name_plural = 'Email Provider Test Results'
    
    def __str__(self):
        return f"{self.provider.name} test to {self.test_email} - {self.get_status_display()}"
