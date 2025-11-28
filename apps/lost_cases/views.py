from django.shortcuts import render
from django.db.models import Q
from apps.renewals.models import RenewalCase 
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LostCaseUpdateSerializer
from apps.renewals.models import Competitor

def lost_cases_dashboard(request):
    queryset = RenewalCase.objects.filter(status='lost')\
        .select_related('customer', 'policy', 'assigned_to')\
        .order_by('-lost_date')

    context = {
        'cases': queryset,
        'total_lost': queryset.count(), 
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
    
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'case_number', 
        'customer__first_name',
        'customer__last_name', 
        'customer__email',
        'policy__policy_number', 
        'competitor__name', 
        'lost_reason'       
    ]

    def get_queryset(self):
        return RenewalCase.objects.filter(status='lost')\
            .select_related('customer', 'policy', 'assigned_to', 'competitor')\
            .order_by('-lost_date')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        stats = queryset.aggregate(
            competitor_offers=Count('id', filter=Q(lost_reason='competitor_offer')),
            price_issues=Count('id', filter=Q(lost_reason='price_too_high')),
            better_coverage=Count('id', filter=Q(lost_reason='better_coverage'))
        )
        total_lost = queryset.count()

        serializer = self.get_serializer(queryset, many=True)
        
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
    
class LostCaseUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = RenewalCase.objects.get(id=case_id)
        except RenewalCase.DoesNotExist:
            return Response({"success": False, "message": "Case not found"}, status=404)

        serializer = LostCaseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Update lost case fields
        case.status = "lost"
        case.lost_reason = data["lost_reason"]
        case.lost_date = data["lost_date"]

        competitor_id = data.get("competitor_id")

        if competitor_id:
            case.competitor = Competitor.objects.get(id=competitor_id)
        else:
            case.competitor = None

        case.save()

        return Response({
            "success": True,
            "message": "Case marked as lost successfully",
            "case_id": case.id,
            "lost_reason": case.get_lost_reason_display(),
            "competitor": case.competitor.name if case.competitor else None,
            "lost_date": case.lost_date,
        }, status=200)
