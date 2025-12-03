from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from apps.renewals.models import RenewalCase
from .serializers import ArchivedCaseListSerializer, ArchiveCaseActionSerializer, ArchiveSingleCaseSerializer
from rest_framework.views import APIView

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

class BulkUpdateCasesView(generics.GenericAPIView):
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

class ArchiveSingleCaseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = RenewalCase.objects.get(id=case_id)
        except RenewalCase.DoesNotExist:
            return Response(
                {"success": False, "message": "Case not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ArchiveSingleCaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        is_archived = data["is_archived"]
        case.is_archived = is_archived

        if is_archived:
            case.archived_reason = data.get("archived_reason")
            case.archived_date = data.get("archived_date") or timezone.now().date()
        else:
            case.archived_reason = None
            case.archived_date = None

        case.save()

        return Response(
            {
                "success": True,
                "message": "Case archived successfully"
                if is_archived
                else "Case unarchived successfully",
                "case_id": case.id,
                "is_archived": case.is_archived,
                "archived_reason": case.archived_reason,
                "archived_date": case.archived_date,
                "final_status": case.get_status_display(),
            },
            status=status.HTTP_200_OK,
        )