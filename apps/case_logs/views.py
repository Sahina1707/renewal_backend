from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.http import HttpRequest
from apps.renewals.models import RenewalCase
from .models import CaseLog
from .serializers import CaseLogSerializer

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_case_logs_by_case_number_api(request: HttpRequest) -> Response:
    try:
        if hasattr(request, 'query_params'):
            case_number = request.query_params.get('case_number', '').strip()  
        else:
            case_number = request.GET.get('case_number', '').strip()  

        if not case_number:
            return Response({
                'error': 'Case number is required',
                'message': 'Please provide a case_number parameter'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            renewal_case = RenewalCase.objects.select_related(
                'customer',
                'policy',
                'policy__policy_type',
                'assigned_to'
            ).get(case_number__iexact=case_number)
        except RenewalCase.DoesNotExist:
            return Response({
                'error': 'Case not found',
                'message': f'No case found with case number: {case_number}'
            }, status=status.HTTP_404_NOT_FOUND)
        except RenewalCase.MultipleObjectsReturned:
            return Response({
                'error': 'Multiple cases found',
                'message': f'Multiple cases found with case number: {case_number}'
            }, status=status.HTTP_400_BAD_REQUEST)

        case_logs = CaseLog.objects.filter(
            renewal_case=renewal_case
        ).select_related(
            'renewal_case',
            'renewal_case__customer',
            'renewal_case__policy',
            'renewal_case__policy__policy_type',
            'created_by',
            'updated_by'
        ).order_by('-created_at')

        logs_count = case_logs.count()

        serializer = CaseLogSerializer(case_logs, many=True)

        response_data = {
            'success': True,
            'search_criteria': {
                'search_type': 'case_number',
                'search_value': case_number,
                'case_found': True
            },
            'case_info': {
                'case_id': renewal_case.id,  
                'case_number': renewal_case.case_number,
                'customer_name': renewal_case.customer.full_name,
                'customer_email': renewal_case.customer.email,
                'customer_phone': renewal_case.customer.phone,
                'policy_number': renewal_case.policy.policy_number,
                'policy_type': renewal_case.policy.policy_type.name if renewal_case.policy.policy_type else None,
                'status': renewal_case.status,
                'status_display': renewal_case.get_status_display(),  
                'assigned_to': renewal_case.assigned_to.get_full_name() if renewal_case.assigned_to else None,
                'created_at': renewal_case.created_at.strftime('%m/%d/%Y, %I:%M:%S %p'),
                'updated_at': renewal_case.updated_at.strftime('%m/%d/%Y, %I:%M:%S %p') if renewal_case.updated_at else None
            },
            'activities': serializer.data,
            'total_activities': logs_count,
            'message': f'Found {logs_count} activities for case {renewal_case.case_number}' if logs_count > 0 else f'No activities found for case {renewal_case.case_number}'
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': 'Failed to search case logs by case number',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_case_logs_by_policy_number_api(request: HttpRequest) -> Response:
    
    try:
        if hasattr(request, 'query_params'):
            policy_number = request.query_params.get('policy_number', '').strip() 
        else:
            policy_number = request.GET.get('policy_number', '').strip()  

        if not policy_number:
            return Response({
                'error': 'Policy number is required',
                'message': 'Please provide a policy_number parameter'
            }, status=status.HTTP_400_BAD_REQUEST)

        renewal_cases = RenewalCase.objects.select_related(
            'customer',
            'policy',
            'policy__policy_type',
            'assigned_to'
        ).filter(policy__policy_number__iexact=policy_number).order_by('-created_at')

        renewal_cases_list = list(renewal_cases)

        if not renewal_cases_list:
            return Response({
                'error': 'Case not found',
                'message': f'No renewal case found for policy number: {policy_number}'
            }, status=status.HTTP_404_NOT_FOUND)

        case_logs = CaseLog.objects.filter(
            renewal_case__in=renewal_cases_list
        ).select_related(
            'renewal_case',
            'renewal_case__customer',
            'renewal_case__policy',
            'renewal_case__policy__policy_type',
            'created_by',
            'updated_by'
        ).order_by('-created_at')

        logs_count = case_logs.count()

        serializer = CaseLogSerializer(case_logs, many=True)

        first_case = renewal_cases_list[0]

        response_data = {
            'success': True,
            'search_criteria': {
                'search_type': 'policy_number',
                'search_value': policy_number,
                'case_found': True
            },
            'case_info': {
                'case_id': first_case.id,
                'case_number': first_case.case_number,
                'policy_number': first_case.policy.policy_number,
                'policy_type': first_case.policy.policy_type.name if first_case.policy.policy_type else None,
                'customer_name': first_case.customer.full_name,
                'customer_email': first_case.customer.email,
                'customer_phone': first_case.customer.phone,
                'status': first_case.status,
                'status_display': first_case.get_status_display(),
                'assigned_to': first_case.assigned_to.get_full_name() if first_case.assigned_to else None,
                'created_at': first_case.created_at.strftime('%m/%d/%Y, %I:%M:%S %p'),
                'updated_at': first_case.updated_at.strftime('%m/%d/%Y, %I:%M:%S %p') if first_case.updated_at else None,
                'total_cases': len(renewal_cases_list),
                'case_numbers': [case.case_number for case in renewal_cases_list]
            },
            'activities': serializer.data,
            'total_activities': logs_count,
            'message': f'Found {logs_count} activities for policy {policy_number} across {len(renewal_cases_list)} renewal case(s)' if logs_count > 0 else f'No activities found for policy {policy_number}'
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': 'Failed to search case logs by policy number',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)