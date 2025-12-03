# views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from .models import User, Role
from .serializers import UserSerializer, UserListSerializer, RoleSerializer


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User management"""
    queryset = User.objects.select_related('role').all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
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


class RoleViewSet(viewsets.ModelViewSet):
    """ViewSet for Role management"""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]