from django.shortcuts import render
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from apps.renewals.models import RenewalCase
from .serializers import NotInterestedCaseSerializer

class NotInterestedCaseListAPIView(generics.ListAPIView):
    serializer_class = NotInterestedCaseSerializer
    permission_classes = [IsAuthenticated]

    # === ADD THIS SEARCH BLOCK ===
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'case_number', 
        'customer__first_name',
        'customer__last_name',
        'customer__email',
        'policy__policy_number',
        'competitor__name',     # This searches "Current Provider"
        'not_interested_reason'
    ]

    def get_queryset(self):
        # Filter strictly for 'not_interested' status
        return RenewalCase.objects.filter(status='not_interested')\
            .select_related('customer', 'policy', 'assigned_to', 'competitor')\
            .order_by('-not_interested_date')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # --- Calculate Dashboard Card Stats ---
        stats = queryset.aggregate(
            already_have_coverage=Count('id', filter=Q(not_interested_reason='already_have_coverage')),
            cannot_afford=Count('id', filter=Q(not_interested_reason='cannot_afford')),
            no_immediate_need=Count('id', filter=Q(not_interested_reason='no_immediate_need'))
        )
        
        total_count = queryset.count()

        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            "success": True,
            "count": total_count,
            "stats": {
                "total_not_interested": total_count,
                "already_have_coverage": stats['already_have_coverage'],
                "cannot_afford": stats['cannot_afford'],
                "no_immediate_need": stats['no_immediate_need']
            },
            "results": serializer.data
        })
