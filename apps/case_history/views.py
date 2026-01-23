from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import CaseHistory
from apps.renewals.models import RenewalCase as Case
from apps.case_logs.models import CaseLog
from .serializers import (
    CaseSerializer,
    CaseListSerializer,
    CaseHistorySerializer,
    CaseStatusUpdateSerializer,
    CaseAssignmentSerializer,
    CaseTimelineSummarySerializer,
    CaseTimelineHistorySerializer,
    UpdateCaseStatusSerializer,
)
from apps.case_logs.serializers import CaseLogSerializer, CaseCommentSerializer, CaseCommentCreateSerializer
class CaseListView(generics.ListCreateAPIView):
    queryset = Case.objects.filter(is_deleted=False)
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'handling_agent', 'customer']
    search_fields = ['case_number', 'notes']
    ordering_fields = ['created_at', 'updated_at', 'started_at', 'processing_days']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CaseListSerializer
        return CaseSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(handling_agent=self.request.user)
        
        return queryset
class CaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'case_number'
    
    def get_queryset(self):
        """Filter cases based on user permissions."""
        queryset = Case.objects.filter(is_deleted=False)
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(handling_agent=self.request.user)
        
        return queryset
    
    def perform_destroy(self, instance):
        """Soft delete the case."""
        instance.delete(user=self.request.user)
class CaseHistoryListView(generics.ListAPIView):
    serializer_class = CaseHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['action', 'created_by']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get history entries for the specified case."""
        case_id = self.kwargs['case_number']
        case = get_object_or_404(Case, case_number=case_id, is_deleted=False)
        
        if not (self.request.user.is_staff or 
                case.handling_agent == self.request.user or 
                case.created_by == self.request.user):
            return CaseHistory.objects.none()
        
        return CaseHistory.objects.filter(case=case, is_deleted=False)
class CaseCommentListView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['comment_type', 'is_internal', 'is_important', 'created_by']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CaseCommentSerializer
        return CaseCommentCreateSerializer
    
    def get_queryset(self):
        """Get comments for the specified case using CaseLog."""
        case_id = self.kwargs['case_number']
        case = get_object_or_404(Case, case_number=case_id, is_deleted=False)
        
        if not (self.request.user.is_staff or 
                case.handling_agent == self.request.user or 
                case.created_by == self.request.user):
            return CaseLog.objects.none()
        return CaseLog.objects.filter(renewal_case=case, is_deleted=False).exclude(comment='').exclude(comment__isnull=True)
    
    def perform_create(self, serializer):
        """Create a new comment for the specified case using CaseLog."""
        case_id = self.kwargs['case_number']
        case = get_object_or_404(Case, case_number=case_id, is_deleted=False)
        
        if not (self.request.user.is_staff or 
                case.handling_agent == self.request.user or 
                case.created_by == self.request.user):
            raise PermissionDenied("You don't have permission to add comments to this case.")
        
        serializer.save(renewal_case=case)
class CaseCommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CaseCommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get comments for the specified case using CaseLog."""
        case_id = self.kwargs['case_number']
        case = get_object_or_404(Case, case_number=case_id, is_deleted=False)
        
      
        if not (self.request.user.is_staff or 
                case.handling_agent == self.request.user or 
                case.created_by == self.request.user):
            return CaseLog.objects.none()
        return CaseLog.objects.filter(renewal_case=case, is_deleted=False).exclude(comment='').exclude(comment__isnull=True)
    
    def perform_update(self, serializer):
        """Update comment and create history entry."""
        comment = serializer.save()
        
        CaseHistory.objects.create(
            case=comment.renewal_case,
            action='comment_updated',
            description=f"Comment updated: {comment.comment[:100]}{'...' if len(comment.comment) > 100 else ''}",
            created_by=self.request.user
        )
    
    def perform_destroy(self, instance):
        CaseHistory.objects.create(
            case=instance.renewal_case,
            action='comment_deleted',
            description=f"Comment deleted: {instance.comment[:100]}{'...' if len(instance.comment) > 100 else ''}",
            created_by=self.request.user
        )
        
        instance.delete(user=self.request.user)

class CaseStatusUpdateView(generics.UpdateAPIView):
    serializer_class = CaseStatusUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'case_number'
    
    def get_queryset(self):
        """Filter cases based on user permissions."""
        queryset = Case.objects.filter(is_deleted=False)
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(handling_agent=self.request.user)
        
        return queryset
class UpdateCaseStatusView(generics.UpdateAPIView):
    serializer_class = UpdateCaseStatusSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'case_number'
    
    def get_queryset(self):
        """Filter cases based on user permissions."""
        queryset = Case.objects.filter(is_deleted=False)
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(assigned_to=self.request.user)
        
        return queryset
    
    def update(self, request, *args, **kwargs):
        """Handle PUT/PATCH request to update case status and related fields."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if not (request.user.is_staff or 
                instance.assigned_to == request.user or 
                instance.created_by == request.user):
            raise PermissionDenied("You don't have permission to update this case.")
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'success': True,
            'message': 'Case status updated successfully',
            'data': {
                'case_number': instance.case_number,
                'status': instance.status,
                'follow_up_date': instance.follow_up_date.isoformat() if instance.follow_up_date else None,
                'follow_up_time': instance.follow_up_time.isoformat() if instance.follow_up_time else None,
                'remarks': instance.remarks,
            }
        }, status=status.HTTP_200_OK)
class CaseAssignmentView(generics.UpdateAPIView):
    serializer_class = CaseAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'case_number'
    
    def get_queryset(self):
        """Only staff can assign cases."""
        if not self.request.user.is_staff:
            return Case.objects.none()
        return Case.objects.filter(is_deleted=False)


class CaseCloseView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, case_id):
        """Close the case."""
        case = get_object_or_404(Case, case_number=case_id, is_deleted=False)
        
        if not (request.user.is_staff or 
                case.handling_agent == request.user or 
                case.created_by == request.user):
            raise PermissionDenied("You don't have permission to close this case.")
        
        if case.is_closed:
            return Response(
                {'error': 'Case is already closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        case.close_case(user=request.user)
        
        CaseHistory.objects.create(
            case=case,
            action='case_closed',
            description=f"Case {case.case_number} closed",
            created_by=request.user
        )
        
        serializer = CaseSerializer(case, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def case_timeline_view(request, case_number):
    case = get_object_or_404(
        Case.objects.select_related('policy__agent', 'customer', 'assigned_to'), 
        case_number=case_number, 
        is_deleted=False
    )
    
    if not (request.user.is_staff or 
            case.assigned_to == request.user or 
            case.created_by == request.user):
        raise PermissionDenied("You don't have permission to view this case.")
    
    history = CaseHistory.objects.filter(case=case, is_deleted=False).select_related('created_by').order_by('created_at')
    history_serializer = CaseTimelineHistorySerializer(history, many=True, context={'request': request})
    
    from datetime import timedelta
    system_events = []
    
    if case.created_at:
        case_created_exists = history.filter(action='case_created').exists()
        if not case_created_exists:
            case_created_date = case.created_at
            
            if hasattr(case, 'batch_code') and case.batch_code:
                description = f"Case uploaded via bulk upload"
            else:
                description = "Case created"
            
            system_events.append({
                'event_type': 'Case Created',
                'event_description': description,
                'event_date': case_created_date.strftime('%d/%m/%Y'),
                'event_time': case_created_date.strftime('%H:%M:%S'),
                'performed_by': 'System',
                'created_at': case_created_date
            })
    
    if case.created_at:
        validation_exists = history.filter(action='validation').exists()
        if not validation_exists:
            validation_date = case.created_at + timedelta(seconds=5)
            system_events.append({
                'event_type': 'Validation',
                'event_description': 'All required fields present and valid',
                'event_date': validation_date.strftime('%d/%m/%Y'),
                'event_time': validation_date.strftime('%H:%M:%S'),
                'performed_by': 'System',
                'created_at': validation_date
            })
    
    if case.assigned_to:
        assignment_exists = history.filter(action__in=['assignment', 'agent_assigned']).exists()
        if not assignment_exists:
            assignment_date = case.updated_at if hasattr(case, 'updated_at') and case.updated_at else case.created_at
            agent_name = case.assigned_to.get_full_name() if hasattr(case.assigned_to, 'get_full_name') else (case.assigned_to.username if hasattr(case.assigned_to, 'username') else str(case.assigned_to))
            system_events.append({
                'event_type': 'Assignment',
                'event_description': f"Case assigned to agent {agent_name}",
                'event_date': assignment_date.strftime('%d/%m/%Y'),
                'event_time': assignment_date.strftime('%H:%M:%S'),
                'performed_by': 'System',
                'created_at': assignment_date
            })
    
    all_history = list(history_serializer.data)
    
    existing_event_types = {h.get('event_type') for h in all_history}
    
    for event in system_events:
        if event['event_type'] not in existing_event_types:
            all_history.append(event)
    
    from datetime import datetime
    def sort_key(event):
        try:
            date_str = event.get('event_date', '')
            time_str = event.get('event_time', '00:00:00')
            if date_str and time_str:
                dt_str = f"{date_str} {time_str}"
                return datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
        except:
            pass
        if 'created_at' in event:
            return event['created_at']
        return datetime.min
    
    all_history.sort(key=sort_key)
    
    for event in all_history:
        if 'created_at' in event:
            del event['created_at']
    
    summary_serializer = CaseTimelineSummarySerializer(case, context={'request': request})
    
    case_logs = CaseLog.objects.filter(renewal_case=case, is_deleted=False).select_related('created_by', 'updated_by').order_by('-created_at')
    case_logs_serializer = CaseLogSerializer(case_logs, many=True, context={'request': request})
    
    return Response({
        'journey_summary': summary_serializer.data,
        'case_history': all_history,
        'case_logs': case_logs_serializer.data,
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def case_stats_view(request, case_number):
    case = get_object_or_404(Case, case_number=case_number, is_deleted=False)
    
    if not (request.user.is_staff or 
            case.handling_agent == request.user or 
            case.created_by == request.user):
        raise PermissionDenied("You don't have permission to view this case.")
    
    total_comments = case.comments.filter(is_deleted=False).count()
    total_history = case.history.filter(is_deleted=False).count()
    internal_comments = case.comments.filter(is_deleted=False, is_internal=True).count()
    important_comments = case.comments.filter(is_deleted=False, is_important=True).count()
    
    status_changes = case.history.filter(
        is_deleted=False,
        action='status_changed'
    ).order_by('created_at')
    
    return Response({
        'case_id': case.case_number,
        'status': case.status,
        'processing_days': case.processing_days,
        'total_comments': total_comments,
        'total_history': total_history,
        'internal_comments': internal_comments,
        'important_comments': important_comments,
        'status_changes': CaseHistorySerializer(status_changes, many=True, context={'request': request}).data,
    })