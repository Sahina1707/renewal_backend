from django.shortcuts import render
from django.db.models import Q
from apps.renewals.models import RenewalCase 

def lost_cases_dashboard(request):
    """
    Backend logic to fetch and structure data for the Lost Cases Dashboard.
    """
    
    # 1. Filter for 'lost' status
    # 2. Select related fields to prevent DB hammering (Customer, Policy, Agent)
    # 3. Order by lost_date desc (newest lost cases first)
    queryset = RenewalCase.objects.filter(status='lost')\
        .select_related('customer', 'policy', 'assigned_to')\
        .order_by('-lost_date')

    # Optional: If you need specific logic for the 'Attempts' column
    # Since 'communication_attempts_count' is a property, it calculates per row.
    # If the list is huge (1000+), consider annotations. For a dashboard page, this is fine.

    context = {
        'cases': queryset,
        'total_lost': queryset.count(), # Helpful for a summary counter
    }

    return render(request, 'lost_cases/dashboard.html', context)
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from apps.renewals.models import RenewalCase
from .serializers import LostCaseListSerializer

class LostCaseListAPIView(generics.ListAPIView):
    serializer_class = LostCaseListSerializer
    permission_classes = [IsAuthenticated]
    
    # === ADD THIS SEARCH BLOCK ===
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'case_number', 
        'customer__first_name',
        'customer__last_name', 
        'customer__email',
        'policy__policy_number', 
        'competitor__name',  # Search by Competitor Name
        'lost_reason'        # Search by reason code
    ]

    def get_queryset(self):
        """
        Return only cases marked as 'lost', ordered by most recent.
        Optimized with select_related to avoid N+1 queries.
        """
        # Optimize queries to fetch Customer, Policy, Agent, and Competitor data
        return RenewalCase.objects.filter(status='lost')\
            .select_related('customer', 'policy', 'assigned_to', 'competitor')\
            .order_by('-lost_date')

    def list(self, request, *args, **kwargs):
        """Custom list method to return the exact JSON wrapper format"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # --- 1. Calculate Dashboard Stats (The Cards) ---
        # We use aggregation to get all counts in a single efficient database query
        stats = queryset.aggregate(
            competitor_offers=Count('id', filter=Q(lost_reason='competitor_offer')),
            price_issues=Count('id', filter=Q(lost_reason='price_too_high')),
            better_coverage=Count('id', filter=Q(lost_reason='better_coverage'))
        )
        
        total_lost = queryset.count()

        # --- 2. Serialize the List Data ---
        serializer = self.get_serializer(queryset, many=True)
        
        # --- 3. Construct the Final JSON ---
        return Response({
            "success": True,
            "count": total_lost,
            "stats": {
                "total_lost_cases": total_lost,
                "competitor_offers": stats['competitor_offers'],
                "price_issues": stats['price_issues'],
                "better_coverage": stats['better_coverage']
            },
            "results": serializer.data
        })