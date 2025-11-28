from django.shortcuts import render
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from apps.renewals.models import RenewalCase
from .serializers import NotInterestedCaseSerializer
from .serializers import NotInterestedCaseUpdateSerializer
from apps.renewals.models import Competitor
from rest_framework.views import APIView
class NotInterestedCaseListAPIView(generics.ListAPIView):
    serializer_class = NotInterestedCaseSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter]
    search_fields = [
        'case_number', 
        'customer__first_name',
        'customer__last_name',
        'customer__email',
        'policy__policy_number',
        'competitor__name',     
        'not_interested_reason'
    ]

    def get_queryset(self):
        return RenewalCase.objects.filter(status='not_interested')\
            .select_related('customer', 'policy', 'assigned_to', 'competitor')\
            .order_by('-not_interested_date')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
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


class NotInterestedCaseUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = RenewalCase.objects.get(id=case_id)
        except RenewalCase.DoesNotExist:
            return Response({"success": False, "message": "Case not found"}, status=404)

        serializer = NotInterestedCaseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        case.status = 'not_interested'
        case.not_interested_reason = data['not_interested_reason']
        case.not_interested_date = data['not_interested_date']

        competitor_id = data.get("competitor_id")
        if competitor_id:
            case.competitor = Competitor.objects.get(id=competitor_id)
        else:
            case.competitor = None

        case.save()

        return Response({
            "success": True,
            "message": "Case marked as Not Interested successfully",
            "case_id": case.id,
            "reason": case.get_not_interested_reason_display(),
            "competitor": case.competitor.name if case.competitor else None,
            "marked_date": case.not_interested_date
        }, status=200)
