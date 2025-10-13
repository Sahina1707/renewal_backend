from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from apps.customers.models import Customer
from apps.policies.models import Policy

User = get_user_model()


class AIInsight(BaseModel):
    
    INSIGHT_TYPE_CHOICES = [
        ('claim_likelihood', 'Claim Likelihood'),
        ('customer_profile', 'Customer Profile'),
        ('renewal_prediction', 'Renewal Prediction'),
        ('risk_assessment', 'Risk Assessment'),
        ('behavior_analysis', 'Behavior Analysis'),
        ('payment_pattern', 'Payment Pattern'),
    ]
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='ai_insights',
        help_text="Customer this insight is about"
    )
    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name='ai_insights',
        null=True,
        blank=True,
        help_text="Policy this insight is about (optional for customer-level insights)"
    )
    insight_type = models.CharField(
        max_length=50,
        choices=INSIGHT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of AI insight"
    )
    insight_title = models.CharField(
        max_length=200,
        help_text="Title of the insight (e.g., 'Claim Likelihood', 'Customer Profile')"
    )
    insight_value = models.CharField(
        max_length=100,
        help_text="Value or result of the insight (e.g., 'Moderate', 'Good', 'High Risk')"
    )
    insight_description = models.TextField(
        help_text="Detailed explanation of the insight"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="AI confidence level (0.0000 to 1.0000)"
    )
    key_observations = models.JSONField(
        default=dict,
        help_text="Structured data for key observations and metrics"
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this insight was generated"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this insight should be displayed"
    )
    
    class Meta:
        db_table = 'ai_insights'
        ordering = ['-generated_at', 'insight_type']
        indexes = [
            models.Index(fields=['customer', 'insight_type']),
            models.Index(fields=['policy', 'insight_type']),
            models.Index(fields=['generated_at']),
        ]
    
    def __str__(self):
        policy_info = f" - {self.policy.policy_number}" if self.policy else ""
        return f"{self.insight_title} for {self.customer.name}{policy_info}"


class AIInsightHistory(BaseModel):
    
    insight = models.ForeignKey(
        AIInsight,
        on_delete=models.CASCADE,
        related_name='history',
        help_text="The insight this history entry belongs to"
    )
    previous_value = models.CharField(
        max_length=100,
        help_text="Previous insight value"
    )
    new_value = models.CharField(
        max_length=100,
        help_text="New insight value"
    )
    previous_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Previous confidence score"
    )
    new_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="New confidence score"
    )
    change_reason = models.TextField(
        blank=True,
        help_text="Reason for the change in insight"
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this change occurred"
    )
    
    class Meta:
        db_table = 'ai_insights_history'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"History for {self.insight.insight_title} - {self.changed_at}"


class AIConversation(BaseModel):
    """Model to store AI conversation sessions"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_conversations',
        help_text="User who initiated this conversation"
    )
    session_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique session identifier for this conversation"
    )
    title = models.CharField(
        max_length=200,
        help_text="Conversation title (auto-generated from first message)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        help_text="Current status of the conversation"
    )
    context_data = models.JSONField(
        default=dict,
        help_text="Additional context data for the conversation"
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this conversation was started"
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last activity timestamp"
    )
    message_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of messages in this conversation"
    )
    
    class Meta:
        db_table = 'ai_conversations'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['session_id']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"AI Conversation: {self.title} - {self.user.username}"
    
    def update_message_count(self):
        """Update the message count for this conversation"""
        self.message_count = self.messages.count()
        self.save(update_fields=['message_count'])


class AIMessage(BaseModel):
    """Model to store individual messages in AI conversations"""
    
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'AI Assistant'),
        ('system', 'System'),
    ]
    
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Conversation this message belongs to"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        db_index=True,
        help_text="Role of the message sender"
    )
    content = models.TextField(
        help_text="Message content"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional metadata (tokens used, model, etc.)"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this message was sent"
    )
    is_edited = models.BooleanField(
        default=False,
        help_text="Whether this message has been edited"
    )
    
    class Meta:
        db_table = 'ai_messages'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
            models.Index(fields=['role', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class AIAnalytics(BaseModel):
    """Model to store AI-generated analytics and insights"""
    
    ANALYTICS_TYPE_CHOICES = [
        ('dashboard_summary', 'Dashboard Summary'),
        ('renewal_analysis', 'Renewal Analysis'),
        ('customer_insights', 'Customer Insights'),
        ('campaign_performance', 'Campaign Performance'),
        ('payment_analysis', 'Payment Analysis'),
        ('predictive_insights', 'Predictive Insights'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_analytics',
        help_text="User who requested this analysis"
    )
    analytics_type = models.CharField(
        max_length=50,
        choices=ANALYTICS_TYPE_CHOICES,
        db_index=True,
        help_text="Type of analytics generated"
    )
    title = models.CharField(
        max_length=200,
        help_text="Title of the analytics report"
    )
    summary = models.TextField(
        help_text="Summary of the analytics findings"
    )
    detailed_analysis = models.JSONField(
        default=dict,
        help_text="Detailed analysis data and metrics"
    )
    insights = models.JSONField(
        default=list,
        help_text="List of key insights generated"
    )
    recommendations = models.JSONField(
        default=list,
        help_text="List of actionable recommendations"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="AI confidence level (0.0000 to 1.0000)"
    )
    data_snapshot = models.JSONField(
        default=dict,
        help_text="Snapshot of data used for analysis"
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this analysis was generated"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this analysis is still relevant"
    )
    
    class Meta:
        db_table = 'ai_analytics'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['user', 'analytics_type']),
            models.Index(fields=['analytics_type', 'generated_at']),
            models.Index(fields=['generated_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"