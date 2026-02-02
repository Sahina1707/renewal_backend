# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from .models import Customer
from .serializers import CustomerSerializer

User = get_user_model()

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('assigned_agent', 'segment').all()
    serializer_class = CustomerSerializer

    @action(detail=False, methods=['post'])
    def update_policy_counts(self, request):
        """Update policy counts for all customers"""
        try:
            customers = Customer.objects.all()
            updated_count = 0

            with transaction.atomic():
                for customer in customers:
                    customer.update_metrics()
                    updated_count += 1

            return Response({
                'message': f'Successfully updated policy counts for {updated_count} customers',
                'updated_count': updated_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Failed to update policy counts: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def update_policy_count(self, request, pk=None):
        """Update policy count for a specific customer"""
        try:
            customer = self.get_object()
            old_count = customer.total_policies
            old_profile = customer.profile
            customer.update_metrics()
            new_count = customer.total_policies
            new_profile = customer.profile

            return Response({
                'message': f'Updated policy count for customer {customer.customer_code}',
                'customer_code': customer.customer_code,
                'old_count': old_count,
                'new_count': new_count,
                'old_profile': old_profile,
                'new_profile': new_profile
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Failed to update policy count: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def profile_summary(self, request):
        """Get summary of customer profiles"""
        try:
            total_customers = Customer.objects.count()
            hni_customers = Customer.objects.filter(profile='HNI').count()
            normal_customers = Customer.objects.filter(profile='Normal').count()

            # Get some examples
            hni_examples = Customer.objects.filter(profile='HNI')[:5]
            normal_examples = Customer.objects.filter(profile='Normal')[:5]

            hni_data = []
            for customer in hni_examples:
                policy_count = customer.policies.filter(is_deleted=False).count()
                hni_data.append({
                    'customer_code': customer.customer_code,
                    'name': customer.full_name,
                    'profile': customer.profile,
                    'policy_count': policy_count
                })

            normal_data = []
            for customer in normal_examples:
                policy_count = customer.policies.filter(is_deleted=False).count()
                normal_data.append({
                    'customer_code': customer.customer_code,
                    'name': customer.full_name,
                    'profile': customer.profile,
                    'policy_count': policy_count
                })

            return Response({
                'summary': {
                    'total_customers': total_customers,
                    'hni_customers': hni_customers,
                    'normal_customers': normal_customers
                },
                'examples': {
                    'hni_customers': hni_data,
                    'normal_customers': normal_data
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Failed to get profile summary: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def assign_agent(self, request, pk=None):
        """Assign an agent to a customer"""
        customer = self.get_object()
        agent_id = request.data.get('agent_id')

        if not agent_id:
            return Response({
                'error': 'agent_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            agent = User.objects.get(id=agent_id, status='active')

            # Check if agent has appropriate role (optional)
            if agent.role and agent.role.name not in ['Agent', 'Manager', 'Admin']:
                return Response({
                    'error': 'Selected user is not authorized to be an agent'
                }, status=status.HTTP_400_BAD_REQUEST)

            old_agent = customer.assigned_agent
            customer.assigned_agent = agent
            customer.save()

            return Response({
                'message': 'Agent assigned successfully',
                'customer_code': customer.customer_code,
                'customer_name': customer.full_name,
                'old_agent': old_agent.get_full_name() if old_agent else None,
                'new_agent': agent.get_full_name(),
                'agent_email': agent.email
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'Agent not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Failed to assign agent: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def unassign_agent(self, request, pk=None):
        """Remove agent assignment from a customer"""
        customer = self.get_object()

        if not customer.assigned_agent:
            return Response({
                'error': 'Customer has no assigned agent'
            }, status=status.HTTP_400_BAD_REQUEST)

        old_agent = customer.assigned_agent
        customer.assigned_agent = None
        customer.save()

        return Response({
            'message': 'Agent unassigned successfully',
            'customer_code': customer.customer_code,
            'customer_name': customer.full_name,
            'removed_agent': old_agent.get_full_name()
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def available_agents(self, request):
        """Get list of available agents for assignment"""
        agents = User.objects.filter(
            status='active',
            is_active=True
        ).select_related('role')

        role_filter = request.query_params.get('role')
        if role_filter:
            agents = agents.filter(role__name__icontains=role_filter)

        agents_with_workload = agents.annotate(
            assigned_customers_count=Count('assigned_customers')
        ).order_by('assigned_customers_count', 'first_name')

        agent_list = []
        for agent in agents_with_workload:
            agent_list.append({
                'id': agent.id,
                'name': agent.get_full_name(),
                'email': agent.email,
                'role': agent.role.name if agent.role else 'No Role',
                'department': agent.department,
                'assigned_customers_count': agent.assigned_customers_count,
                'status': agent.status
            })

        return Response({
            'agents': agent_list,
            'total_agents': len(agent_list)
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def unassigned_customers(self, request):
        """Get customers without assigned agents"""
        unassigned = Customer.objects.filter(
            assigned_agent__isnull=True,
            status='active'
        ).select_related('segment')

        # Optional filtering
        priority = request.query_params.get('priority')
        if priority:
            unassigned = unassigned.filter(priority=priority)

        profile = request.query_params.get('profile')
        if profile:
            unassigned = unassigned.filter(profile=profile)

        customer_list = []
        for customer in unassigned:
            customer_list.append({
                'id': customer.id,
                'customer_code': customer.customer_code,
                'name': customer.full_name,
                'email': customer.email,
                'phone': customer.phone,
                'priority': customer.priority,
                'profile': customer.profile,
                'total_policies': customer.total_policies,
                'city': customer.city,
                'state': customer.state
            })

        return Response({
            'unassigned_customers': customer_list,
            'total_unassigned': len(customer_list)
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def agent_workload(self, request):
        """Get agent workload statistics"""
        agents_workload = User.objects.filter(
            status='active',
            assigned_customers__isnull=False
        ).annotate(
            customers_count=Count('assigned_customers'),
            active_customers=Count('assigned_customers', filter=Q(assigned_customers__status='active')),
            vip_customers=Count('assigned_customers', filter=Q(assigned_customers__priority='vip')),
            hni_customers=Count('assigned_customers', filter=Q(assigned_customers__profile='HNI'))
        ).order_by('-customers_count')

        workload_data = []
        for agent in agents_workload:
            workload_data.append({
                'agent_id': agent.id,
                'agent_name': agent.get_full_name(),
                'agent_email': agent.email,
                'role': agent.role.name if agent.role else 'No Role',
                'total_customers': agent.customers_count,
                'active_customers': agent.active_customers,
                'vip_customers': agent.vip_customers,
                'hni_customers': agent.hni_customers
            })

        return Response({
            'agent_workload': workload_data,
            'total_agents_with_customers': len(workload_data)
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def bulk_assign_agents(self, request):
        """Bulk assign agents to multiple customers"""
        assignments = request.data.get('assignments', [])

        if not assignments:
            return Response({
                'error': 'assignments list is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        successful_assignments = []
        failed_assignments = []

        with transaction.atomic():
            for assignment in assignments:
                customer_id = assignment.get('customer_id')
                agent_id = assignment.get('agent_id')

                try:
                    customer = Customer.objects.get(id=customer_id)
                    agent = User.objects.get(id=agent_id, status='active')

                    customer.assigned_agent = agent
                    customer.save()

                    successful_assignments.append({
                        'customer_id': customer_id,
                        'customer_code': customer.customer_code,
                        'customer_name': customer.full_name,
                        'agent_name': agent.get_full_name(),
                        'agent_email': agent.email
                    })

                except (Customer.DoesNotExist, User.DoesNotExist) as e:
                    failed_assignments.append({
                        'customer_id': customer_id,
                        'agent_id': agent_id,
                        'error': str(e)
                    })

        return Response({
            'message': f'Bulk assignment completed. {len(successful_assignments)} successful, {len(failed_assignments)} failed',
            'successful_assignments': successful_assignments,
            'failed_assignments': failed_assignments
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def auto_assign_agents(self, request):
        """Automatically assign agents to unassigned customers using round-robin distribution"""
        try:
            # Get available agents (active users)
            available_agents = User.objects.filter(
                status='active',
                is_active=True
            ).annotate(
                current_workload=Count('assigned_customers')
            ).order_by('current_workload', 'first_name')

            if not available_agents.exists():
                return Response({
                    'error': 'No active agents available for assignment'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get unassigned customers
            unassigned_customers = Customer.objects.filter(
                assigned_agent__isnull=True
            ).order_by('created_at')

            if not unassigned_customers.exists():
                return Response({
                    'message': 'No unassigned customers found',
                    'assigned_count': 0
                }, status=status.HTTP_200_OK)

            # Auto-assign using round-robin
            successful_assignments = []
            failed_assignments = []
            agent_index = 0

            with transaction.atomic():
                for customer in unassigned_customers:
                    try:
                        # Get the next agent in round-robin fashion
                        agent = available_agents[agent_index % available_agents.count()]

                        customer.assigned_agent = agent
                        customer.save()

                        successful_assignments.append({
                            'customer_id': customer.id,
                            'customer_code': customer.customer_code,
                            'customer_name': customer.full_name,
                            'agent_id': agent.id,
                            'agent_name': agent.get_full_name(),
                            'agent_email': agent.email
                        })

                        agent_index += 1

                    except Exception as e:
                        failed_assignments.append({
                            'customer_id': customer.id,
                            'customer_code': customer.customer_code,
                            'error': str(e)
                        })

            return Response({
                'message': f'Auto-assignment completed. {len(successful_assignments)} successful, {len(failed_assignments)} failed',
                'total_agents_used': available_agents.count(),
                'successful_assignments': successful_assignments,
                'failed_assignments': failed_assignments,
                'assignment_summary': {
                    'total_assigned': len(successful_assignments),
                    'total_failed': len(failed_assignments),
                    'agents_used': available_agents.count()
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Auto-assignment failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def auto_assign_unassigned_customers(self, request):
        """Automatically assign agents to all unassigned customers"""
        try:
            # Get available agents
            available_agents = User.objects.filter(
                status='active',
                is_active=True
            ).annotate(
                current_workload=Count('assigned_customers')
            ).order_by('current_workload', 'first_name')

            if not available_agents.exists():
                return Response({
                    'error': 'No active agents available for assignment'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get unassigned customers
            unassigned_customers = Customer.objects.filter(
                assigned_agent__isnull=True
            ).order_by('created_at')

            if not unassigned_customers.exists():
                return Response({
                    'message': 'No unassigned customers found',
                    'assigned_count': 0
                }, status=status.HTTP_200_OK)

            # Auto-assign using round-robin
            successful_assignments = []
            failed_assignments = []
            agent_index = 0

            with transaction.atomic():
                for customer in unassigned_customers:
                    try:
                        agent = available_agents[agent_index % available_agents.count()]

                        customer.assigned_agent = agent
                        customer.save()

                        successful_assignments.append({
                            'customer_id': customer.id,
                            'customer_code': customer.customer_code,
                            'customer_name': customer.full_name,
                            'agent_id': agent.id,
                            'agent_name': agent.get_full_name(),
                            'agent_email': agent.email
                        })

                        agent_index += 1

                    except Exception as e:
                        failed_assignments.append({
                            'customer_id': customer.id,
                            'customer_code': customer.customer_code,
                            'error': str(e)
                        })

            return Response({
                'message': f'Auto-assignment completed. {len(successful_assignments)} successful, {len(failed_assignments)} failed',
                'total_agents_used': available_agents.count(),
                'successful_assignments': successful_assignments,
                'failed_assignments': failed_assignments,
                'assignment_summary': {
                    'total_assigned': len(successful_assignments),
                    'total_failed': len(failed_assignments),
                    'agents_used': available_agents.count()
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Auto-assignment failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
