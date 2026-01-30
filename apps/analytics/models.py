from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel, TimestampedModel
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.campaigns.models import Campaign
import uuid
import json

User = get_user_model()

class Dashboard(BaseModel):
    """Custom dashboards for different user roles"""
    DASHBOARD_TYPE_CHOICES = [
        ('executive', 'Executive Dashboard'),
        ('sales', 'Sales Dashboard'),
        ('operations', 'Operations Dashboard'),
        ('customer_service', 'Customer Service Dashboard'),
        ('marketing', 'Marketing Dashboard'),
        ('custom', 'Custom Dashboard'),
    ]
    
    name = models.CharField(max_length=200)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    layout_config = models.JSONField(default=dict)
    
    is_public = models.BooleanField(default=False)
    allowed_roles = models.JSONField(default=list, blank=True)
    allowed_users = models.ManyToManyField(User, blank=True, related_name='accessible_dashboards')
    
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.PositiveIntegerField(default=300, help_text="Refresh interval in seconds")
    
    view_count = models.PositiveIntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_dashboards')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'dashboards'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.dashboard_type})"
class Widget(BaseModel):
    """Dashboard widgets"""
    WIDGET_TYPE_CHOICES = [
        ('metric', 'Single Metric'),
        ('chart', 'Chart'),
        ('table', 'Data Table'),
        ('list', 'List'),
        ('progress', 'Progress Bar'),
        ('gauge', 'Gauge'),
        ('map', 'Map'),
        ('calendar', 'Calendar'),
        ('text', 'Text/HTML'),
    ]
    
    CHART_TYPE_CHOICES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('area', 'Area Chart'),
        ('scatter', 'Scatter Plot'),
        ('funnel', 'Funnel Chart'),
    ]
    
    name = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES)
    chart_type = models.CharField(max_length=20, choices=CHART_TYPE_CHOICES, blank=True)
    
    data_source = models.CharField(max_length=100, choices=[
        ('policies', 'Policies'),
        ('customers', 'Customers'),
        ('campaigns', 'Campaigns'),
        ('renewals', 'Renewals'),
        ('claims', 'Claims'),
        ('payments', 'Payments'),
        ('surveys', 'Surveys'),
        ('custom_query', 'Custom Query'),
        ('api_endpoint', 'API Endpoint'),
    ])
    
    query_config = models.JSONField(default=dict)
    
    custom_query = models.TextField(blank=True, help_text="Custom SQL query for advanced widgets")
    api_endpoint = models.URLField(blank=True, help_text="External API endpoint for data")
    
    display_config = models.JSONField(default=dict)
    
    default_width = models.PositiveIntegerField(default=1)
    default_height = models.PositiveIntegerField(default=1)
    
    cache_duration = models.PositiveIntegerField(default=300, help_text="Cache duration in seconds")
    last_updated = models.DateTimeField(null=True, blank=True)
    cached_data = models.JSONField(default=dict, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'widgets'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.widget_type})"

class DashboardWidget(BaseModel):
    """Relationship between dashboards and widgets"""
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='dashboard_widgets')
    widget = models.ForeignKey(Widget, on_delete=models.CASCADE, related_name='widget_dashboards')
    
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=1)
    height = models.PositiveIntegerField(default=1)
    
    title_override = models.CharField(max_length=200, blank=True)
    config_override = models.JSONField(default=dict, blank=True)
    
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'dashboard_widgets'
        unique_together = ['dashboard', 'widget']
        ordering = ['dashboard', 'order']
    
    def __str__(self):
        return f"{self.dashboard.name} - {self.widget.name}"

class KPI(BaseModel):
    """Key Performance Indicators"""
    KPI_TYPE_CHOICES = [
        ('revenue', 'Revenue'),
        ('growth', 'Growth Rate'),
        ('retention', 'Retention Rate'),
        ('conversion', 'Conversion Rate'),
        ('satisfaction', 'Customer Satisfaction'),
        ('efficiency', 'Efficiency'),
        ('cost', 'Cost Metric'),
        ('custom', 'Custom KPI'),
    ]
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    name = models.CharField(max_length=200)
    kpi_type = models.CharField(max_length=20, choices=KPI_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    calculation_method = models.TextField(help_text="Description of how this KPI is calculated")
    sql_query = models.TextField(blank=True, help_text="SQL query to calculate the KPI")
    
    target_value = models.FloatField(null=True, blank=True)
    warning_threshold = models.FloatField(null=True, blank=True)
    critical_threshold = models.FloatField(null=True, blank=True)
    
    unit = models.CharField(max_length=20, blank=True, help_text="Unit of measurement (%, $, etc.)")
    decimal_places = models.PositiveIntegerField(default=2)
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_kpis')
    department = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'kpis'
        ordering = ['name']
        verbose_name = 'KPI'
        verbose_name_plural = 'KPIs'
    
    def __str__(self):
        return self.name

class KPIValue(BaseModel):
    """Historical KPI values"""
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='values')
    date = models.DateField()
    value = models.FloatField()
    
    target_value = models.FloatField(null=True, blank=True)
    previous_value = models.FloatField(null=True, blank=True)
    change_percentage = models.FloatField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=[
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], blank=True)
    
    calculation_details = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'kpi_values'
        unique_together = ['kpi', 'date']
        ordering = ['kpi', '-date']
    
    def __str__(self):
        return f"{self.kpi.name} - {self.date}: {self.value}"

class Report(BaseModel):
    """Generated reports"""
    REPORT_TYPE_CHOICES = [
        ('policy', 'Policy Report'),
        ('customer', 'Customer Report'),
        ('financial', 'Financial Report'),
        ('campaign', 'Campaign Report'),
        ('renewal', 'Renewal Report'),
        ('claims', 'Claims Report'),
        ('survey', 'Survey Report'),
        ('performance', 'Performance Report'),
        ('custom', 'Custom Report'),
    ]
    
    FREQUENCY_CHOICES = [
        ('on_demand', 'On Demand'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    parameters = models.JSONField(default=dict)
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='on_demand')
    is_automated = models.BooleanField(default=False)
    next_run_date = models.DateTimeField(null=True, blank=True)
    
    recipients = models.JSONField(default=list, blank=True)
    
    template_config = models.JSONField(default=dict)
    custom_template = models.TextField(blank=True)
    
    last_generated_file = models.FileField(upload_to='reports/', null=True, blank=True)
    file_format = models.CharField(max_length=10, choices=[
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('html', 'HTML'),
    ], default='pdf')
    
    generation_count = models.PositiveIntegerField(default=0)
    last_generated = models.DateTimeField(null=True, blank=True)
    last_generation_duration = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in seconds")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_reports')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.report_type})"
class ReportExecution(BaseModel):
    """Report execution history"""
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in seconds")
    
    execution_parameters = models.JSONField(default=dict)
    
    generated_file = models.FileField(upload_to='reports/executions/', null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    delivery_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ], default='pending')
    
    executed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'report_executions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.report.name} - {self.status} - {self.created_at}"
class AnalyticsEvent(BaseModel):
    """Analytics events for tracking user behavior"""
    EVENT_TYPE_CHOICES = [
        ('page_view', 'Page View'),
        ('button_click', 'Button Click'),
        ('form_submit', 'Form Submit'),
        ('file_download', 'File Download'),
        ('search', 'Search'),
        ('filter', 'Filter Applied'),
        ('export', 'Data Export'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('custom', 'Custom Event'),
    ]
    
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    event_name = models.CharField(max_length=200)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    page_url = models.URLField(blank=True)
    page_title = models.CharField(max_length=200, blank=True)
    referrer = models.URLField(blank=True)
    
    event_data = models.JSONField(default=dict, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['page_url', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.event_name} - {self.timestamp}"

class AlertRule(BaseModel):
    """Alert rules for automated notifications"""
    CONDITION_TYPE_CHOICES = [
        ('threshold', 'Threshold'),
        ('change', 'Change Detection'),
        ('anomaly', 'Anomaly Detection'),
        ('custom', 'Custom Condition'),
    ]
    
    NOTIFICATION_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('slack', 'Slack'),
        ('webhook', 'Webhook'),
        ('in_app', 'In-App Notification'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Data source
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, null=True, blank=True, related_name='alert_rules')
    widget = models.ForeignKey(Widget, on_delete=models.CASCADE, null=True, blank=True, related_name='alert_rules')
    custom_query = models.TextField(blank=True)
    
    # Condition
    condition_type = models.CharField(max_length=20, choices=CONDITION_TYPE_CHOICES)
    condition_config = models.JSONField(default=dict)
    
    # Notification settings
    notification_types = models.JSONField(default=list)
    recipients = models.JSONField(default=list)
    
    # Alert frequency
    check_frequency = models.PositiveIntegerField(default=300, help_text="Check frequency in seconds")
    cooldown_period = models.PositiveIntegerField(default=3600, help_text="Cooldown period in seconds")
    
    # Status
    is_active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'alert_rules'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Alert(BaseModel):
    """Generated alerts"""
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    alert_rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='alerts')
    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Alert data
    trigger_value = models.FloatField(null=True, blank=True)
    threshold_value = models.FloatField(null=True, blank=True)
    alert_data = models.JSONField(default=dict, blank=True)
    
    # Response tracking
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Notification tracking
    notifications_sent = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['alert_rule', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.severity}) - {self.status}"

class DataExport(BaseModel):
    """Data export requests"""
    EXPORT_TYPE_CHOICES = [
        ('policies', 'Policies'),
        ('customers', 'Customers'),
        ('campaigns', 'Campaigns'),
        ('renewals', 'Renewals'),
        ('claims', 'Claims'),
        ('surveys', 'Surveys'),
        ('analytics', 'Analytics'),
        ('custom', 'Custom Query'),
    ]
    
    EXPORT_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('pdf', 'PDF'),
    ]
    
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    name = models.CharField(max_length=200)
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPE_CHOICES)
    export_format = models.CharField(max_length=10, choices=EXPORT_FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    
    # Export configuration
    filters = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    custom_query = models.TextField(blank=True)
    
    # Processing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_duration = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in seconds")
    
    # Results
    exported_file = models.FileField(upload_to='exports/', null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    record_count = models.PositiveIntegerField(null=True, blank=True)
    
    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='data_exports')
    
    class Meta:
        db_table = 'data_exports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.export_type}) - {self.status}" 