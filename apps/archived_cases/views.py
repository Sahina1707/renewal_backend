from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from apps.renewals.models import RenewalCase
from .serializers import ArchivedCaseListSerializer, ArchiveCaseActionSerializer
class ArchivedCaseListAPIView(generics.ListAPIView):
    serializer_class = ArchivedCaseListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'case_number', 
        'customer__first_name',
        'customer__last_name',
        'policy__policy_number', 
        'archived_reason'
    ]

    def get_queryset(self):
        # Filter ONLY archived cases
        return RenewalCase.objects.filter(is_archived=True)\
            .select_related('customer', 'policy', 'assigned_to')\
            .order_by('-archived_date')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        stats = queryset.aggregate(
            successfully_renewed=Count('id', filter=Q(status='renewed')),
            expired=Count('id', filter=Q(status='expired')),
            declined=Count('id', filter=Q(status='declined'))
        )
        
        total_count = queryset.count()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            "success": True,
            "count": total_count,
            "stats": {
                "total_archived": total_count,
                "successfully_renewed": stats['successfully_renewed'],
                "expired": stats['expired'],
                "declined": stats['declined']
            },
            "results": serializer.data
        })

# --- 2. The Action Views (To Archive and Unarchive Cases)
class BulkUpdateCasesView(generics.GenericAPIView):
    """
    A generic view to handle bulk updates for archiving and unarchiving cases.
    Expects a POST request with a list of 'case_ids'.
    """
    queryset = RenewalCase.objects.all()
    serializer_class = ArchiveCaseActionSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case_ids = serializer.validated_data['case_ids']
        
        update_fields = self.get_update_fields(request, serializer)

        updated_count = RenewalCase.objects.filter(case_number__in=case_ids).update(**update_fields)

        if updated_count == 0:
            return Response({"success": False, "message": "No matching cases found to update."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"success": True, "message": f"{updated_count} cases updated successfully."})

class ArchiveCasesView(BulkUpdateCasesView):
    def get_update_fields(self, request, serializer):
        return {"is_archived": True, "archived_reason": serializer.validated_data.get('archived_reason'), "archived_date": timezone.now().date()}

class UnarchiveCasesView(BulkUpdateCasesView):
    def get_update_fields(self, request, serializer):
        return {"is_archived": False, "archived_reason": None, "archived_date": None}
