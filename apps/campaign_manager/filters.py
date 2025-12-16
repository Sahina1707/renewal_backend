# File: apps/campaign_manager/filters.py

import django_filters
from .models import Campaign, CampaignLog, SequenceStep
from django.db.models import Q
class CampaignFilter(django_filters.FilterSet):
    """
    Filter class for CampaignViewSet to handle search, status, and advanced filters.
    """
    search = django_filters.CharFilter(
        method='filter_search', 
        label='Search by Name or Description'
    )
    def filter_search(self, queryset, name, value):
        """Filters campaigns by name or description using Q objects."""
        if value:
            # Use the imported Q object here
            return queryset.filter(
                Q(name__icontains=value) | 
                Q(description__icontains=value)
            )
        return queryset

    # 2. Channel Filter (Email, SMS, WhatsApp)
    # This checks if the respective enable field is True
    channel = django_filters.CharFilter(
        method='filter_by_channel', 
        label='Filter by Channel'
    )

    # 3. Campaign Type Filter (Uses the built-in field)
    campaign_type = django_filters.MultipleChoiceFilter(
        choices=Campaign.CampaignTypes.choices
    )

    # 4. Audience Size Filters (Requires Annotations in the View - added below)
    min_audience_size = django_filters.NumberFilter(
        field_name='audience_contact_count', 
        lookup_expr='gte'
    )
    max_audience_size = django_filters.NumberFilter(
        field_name='audience_contact_count', 
        lookup_expr='lte'
    )
    
    # NOTE: Performance/Tags filters are complex and would require custom 
    # models/annotations not shown in the provided files, so we skip them here.

    class Meta:
        model = Campaign
        fields = ['status', 'campaign_type'] # Built-in filter fields

    def filter_by_channel(self, queryset, name, value):
        """Filters by enabled channel (email, sms, whatsapp)."""
        if value == 'email':
            return queryset.filter(enable_email=True)
        elif value == 'sms':
            return queryset.filter(enable_sms=True)
        elif value == 'whatsapp':
            return queryset.filter(enable_whatsapp=True)
        return queryset