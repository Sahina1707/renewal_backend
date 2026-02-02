import django_filters
from .models import Campaign, CampaignLog, SequenceStep
from django.db.models import Q
class CampaignFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method='filter_search', 
        label='Search by Name or Description'
    )
    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(name__icontains=value) | 
                Q(description__icontains=value)
            )
        return queryset
    channel = django_filters.CharFilter(
        method='filter_by_channel', 
        label='Filter by Channel'
    )

    campaign_type = django_filters.MultipleChoiceFilter(
        choices=Campaign.CampaignTypes.choices
    )
    min_audience_size = django_filters.NumberFilter(
        field_name='audience_contact_count', 
        lookup_expr='gte'
    )
    max_audience_size = django_filters.NumberFilter(
        field_name='audience_contact_count', 
        lookup_expr='lte'
    )

    class Meta:
        model = Campaign
        fields = ['status', 'campaign_type']

    def filter_by_channel(self, queryset, name, value):
        """Filters by enabled channel (email, sms, whatsapp)."""
        if value == 'email':
            return queryset.filter(enable_email=True)
        elif value == 'sms':
            return queryset.filter(enable_sms=True)
        elif value == 'whatsapp':
            return queryset.filter(enable_whatsapp=True)
        return queryset