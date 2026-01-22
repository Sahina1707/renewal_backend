# views.py
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from .models import User, Role
from .serializers import UserSerializer, UserListSerializer, RoleSerializer


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User management"""
    queryset = User.objects.select_related('role').all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['role', 'status']
    search_fields = ['email', 'first_name', 'last_name']
    
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return UserListSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def agents(self, request):
        """Get list of users who can be assigned as agents"""
        # Filter active users who can be agents
        agents = User.objects.filter(
            status='active',
            is_active=True
        ).select_related('role')
        
        # Optional role filtering
        role_filter = request.query_params.get('role')
        if role_filter:
            agents = agents.filter(role__name__icontains=role_filter)
        
        # Add customer count annotation
        agents_with_workload = agents.annotate(
            assigned_customers_count=Count('assigned_customers')
        ).order_by('assigned_customers_count', 'first_name')
        
        agent_list = []
        for agent in agents_with_workload:
            agent_list.append({
                'id': agent.id,
                'name': agent.get_full_name(),
                'email': agent.email,
                'first_name': agent.first_name,
                'last_name': agent.last_name,
                'role': agent.role.name if agent.role else 'No Role',
                'department': agent.department,
                'job_title': agent.job_title,
                'assigned_customers_count': agent.assigned_customers_count,
                'status': agent.status,
                'phone': agent.phone
            })
        
        return Response({
            'agents': agent_list,
            'total_agents': len(agent_list)
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def roles(self, request):
        """Get list of available roles"""
        roles = Role.objects.all().order_by('name')
        serializer = RoleSerializer(roles, many=True)
        
        return Response({
            'roles': serializer.data,
            'total_roles': roles.count()
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def workload(self, request, pk=None):
        """Get workload details for a specific agent"""
        user = self.get_object()
        
        # Get customer assignment statistics
        workload_stats = {
            'agent_id': user.id,
            'agent_name': user.get_full_name(),
            'agent_email': user.email,
            'role': user.role.name if user.role else 'No Role',
            'department': user.department,
            'total_customers': user.assigned_customers.count(),
            'active_customers': user.assigned_customers.filter(status='active').count(),
            'vip_customers': user.assigned_customers.filter(priority='vip').count(),
            'hni_customers': user.assigned_customers.filter(profile='HNI').count(),
            'customers_by_status': {},
            'customers_by_priority': {},
            'customers_by_profile': {}
        }
        
        # Get detailed breakdowns
        # Note: Depending on your app structure, ensure 'apps.customers' exists
        try:
            from apps.customers.models import Customer
            
            # Status breakdown
            status_counts = user.assigned_customers.values('status').annotate(
                count=Count('id')
            ).order_by('status')
            workload_stats['customers_by_status'] = {
                item['status']: item['count'] for item in status_counts
            }
            
            # Priority breakdown
            priority_counts = user.assigned_customers.values('priority').annotate(
                count=Count('id')
            ).order_by('priority')
            workload_stats['customers_by_priority'] = {
                item['priority']: item['count'] for item in priority_counts
            }
            
            # Profile breakdown
            profile_counts = user.assigned_customers.values('profile').annotate(
                count=Count('id')
            ).order_by('profile')
            workload_stats['customers_by_profile'] = {
                item['profile']: item['count'] for item in profile_counts
            }
        except ImportError:
            # Fallback if customers app isn't ready yet
            pass
        
        return Response(workload_stats, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def workload_summary(self, request):
        """Get workload summary for all agents"""
        agents_with_customers = User.objects.filter(
            status='active',
            assigned_customers__isnull=False
        ).annotate(
            customers_count=Count('assigned_customers'),
            active_customers=Count('assigned_customers', filter=Q(assigned_customers__status='active')),
            vip_customers=Count('assigned_customers', filter=Q(assigned_customers__priority='vip')),
            hni_customers=Count('assigned_customers', filter=Q(assigned_customers__profile='HNI'))
        ).order_by('-customers_count')
        
        workload_data = []
        for agent in agents_with_customers:
            workload_data.append({
                'agent_id': agent.id,
                'agent_name': agent.get_full_name(),
                'agent_email': agent.email,
                'role': agent.role.name if agent.role else 'No Role',
                'department': agent.department,
                'total_customers': agent.customers_count,
                'active_customers': agent.active_customers,
                'vip_customers': agent.vip_customers,
                'hni_customers': agent.hni_customers
            })
        
        return Response({
            'agent_workload': workload_data,
            'total_agents_with_customers': len(workload_data),
            'summary': {
                'total_agents': len(workload_data),
                'total_assigned_customers': sum(item['total_customers'] for item in workload_data),
                'avg_customers_per_agent': sum(item['total_customers'] for item in workload_data) / len(workload_data) if workload_data else 0
            }
        }, status=status.HTTP_200_OK)
    @action(detail=False, methods=['get'])
    def departments(self, request):
        """
        Return list of departments for the frontend dropdown
        """
        departments = [
            {"value": key, "label": label} 
            for key, label in User.DEPARTMENT_CHOICES
        ]
        return Response(departments)
    @action(detail=False, methods=['get'])
    def languages(self, request):
        """
        Returns the complete list of portal languages as shown in the UI.
        """
        languages = [
            {"value": "en", "label": "English"},
            {"value": "hi", "label": "Hindi (हिंदी)"},
            {"value": "bn", "label": "Bengali (বাংলা)"},
            {"value": "te", "label": "Telugu (తెలుగు)"},
            {"value": "mr", "label": "Marathi (मराठी)"},
            {"value": "ta", "label": "Tamil (தமிழ்)"},
            {"value": "gu", "label": "Gujarati (ગુજરાતી)"},
            {"value": "ml", "label": "Malayalam (മലയാളം)"},
            {"value": "kn", "label": "Kannada (ಕನ್ನಡ)"},
            {"value": "pa", "label": "Punjabi (ਪੰਜਾਬੀ)"},
            {"value": "as", "label": "Assamese (অসমীয়া)"},
            {"value": "or", "label": "Odia (ଓଡ଼ିଆ)"},
            {"value": "ur", "label": "Urdu (اردو)"},
        ]
        return Response(languages)
    
class RoleViewSet(viewsets.ModelViewSet):
    """ViewSet for Role management"""
    queryset = Role.objects.all().order_by('id') 
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    # pagination_class = CustomPageNumberPagination
    @action(detail=True, methods=['post'], url_path='reset')
    def reset_to_default(self, request, pk=None):
        """Reset a system role to its default permissions"""
        role = self.get_object()
        
        if not role.is_system:
            return Response(
                {'error': 'Only system roles can be reset to default.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        role.permissions = role.default_permissions
        role.save()
        
        serializer = self.get_serializer(role)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        """Block deletion of System Roles"""
        if instance.is_system:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                "error": "System roles cannot be deleted. You can only reset them."
            })
        
        if instance.users.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                "error": f"Cannot delete role '{instance.display_name}' because users are assigned to it."
            })
            
        instance.delete()
    @action(detail=False, methods=['get'], url_path='permissions')
    def available_permissions(self, request):
        """
        Returns the exact permission structure to match the UI screenshots.
        """
        permission_structure = {
            "Core Pages": [
                {"key": "dashboard", "label": "Dashboard", "description": "View main dashboard with analytics and overview"},
                {"key": "upload_data", "label": "Upload Data", "description": "Upload policy and case data files"},
                {"key": "case_tracking", "label": "Case Tracking", "description": "View and manage active cases"},
                {"key": "closed_cases", "label": "Closed Cases", "description": "View and manage closed cases"},
                {"key": "policy_timeline", "label": "Policy Timeline", "description": "View policy timeline and history"},
                {"key": "case_logs", "label": "Case Logs", "description": "View system and case logs"},
                {"key": "claims_management", "label": "Claims Management", "description": "Manage insurance claims processing"},
                {"key": "policy_servicing", "label": "Policy Servicing", "description": "Manage policy servicing and maintenance"},
                {"key": "new_business", "label": "New Business", "description": "Handle new business applications and processing"},
                {"key": "medical_management", "label": "Medical Management", "description": "Manage medical underwriting and assessments"},
            ],
            "Email Pages": [
                {"key": "email_inbox", "label": "Email Inbox", "description": "Access email inbox and management"},
                {"key": "email_dashboard", "label": "Email Dashboard", "description": "View email analytics and dashboard"},
                {"key": "email_analytics", "label": "Email Analytics", "description": "View detailed email analytics and reports"},
                {"key": "bulk_email", "label": "Bulk Email", "description": "Send bulk emails and campaigns"},
            ],
            "Marketing Pages": [
                {"key": "campaigns", "label": "Campaigns", "description": "Manage marketing campaigns"},
                {"key": "template_manager", "label": "Template Manager", "description": "Manage email and document templates"},
            ],
            "Survey Pages": [
                {"key": "feedback_surveys", "label": "Feedback & Surveys", "description": "Manage customer feedback and surveys"},
                {"key": "survey_designer", "label": "Survey Designer", "description": "Create and design custom surveys"},
            ],
            "Communication Pages": [
                {"key": "whatsapp_flow", "label": "WhatsApp Flow", "description": "Manage automated WhatsApp messaging flows"},
            ],
            "Renewal Pages": [
                {"key": "email_manager", "label": "Email Manager", "description": "Manage email communications for policy renewals"},
                {"key": "whatsapp_manager", "label": "WhatsApp Manager", "description": "Manage WhatsApp communications for policy renewals"},
            ],
            "Admin Pages": [
                {"key": "settings", "label": "Settings", "description": "Access system settings and configuration"},
                {"key": "billing", "label": "Billing", "description": "View billing information and invoices"},
                {"key": "user_management", "label": "User Management", "description": "Manage users and permissions"},
            ],
            "Personal Pages": [
                {"key": "profile", "label": "Profile", "description": "Manage personal profile and account settings"},
            ]
        }
        return Response(permission_structure)