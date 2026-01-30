from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from apps.core.pagination import StandardResultsSetPagination
from .models import CustomerFamilyMedicalHistory
from .serializers import (
    CustomerFamilyMedicalHistorySerializer,
    CustomerFamilyMedicalHistoryCreateSerializer,
    CustomerFamilyMedicalHistoryListSerializer,
)
class CustomerFamilyMedicalHistoryViewSet(viewsets.ModelViewSet):
    queryset = CustomerFamilyMedicalHistory.objects.filter(is_deleted=False)
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomerFamilyMedicalHistoryCreateSerializer
        elif self.action == 'list':
            return CustomerFamilyMedicalHistoryListSerializer
        return CustomerFamilyMedicalHistorySerializer

    def get_queryset(self):
        queryset = CustomerFamilyMedicalHistory.objects.filter(is_deleted=False)

        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        condition_category = self.request.query_params.get('condition_category')
        if condition_category:
            queryset = queryset.filter(condition_category=condition_category)

        condition_status = self.request.query_params.get('condition_status')
        if condition_status:
            queryset = queryset.filter(condition_status=condition_status)

        family_relation = self.request.query_params.get('family_relation')
        if family_relation:
            queryset = queryset.filter(family_relation=family_relation)

        severity_level = self.request.query_params.get('severity_level')
        if severity_level:
            queryset = queryset.filter(severity_level=severity_level)

        insurance_impact = self.request.query_params.get('insurance_impact')
        if insurance_impact:
            queryset = queryset.filter(insurance_impact=insurance_impact)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        min_age = self.request.query_params.get('min_age')
        max_age = self.request.query_params.get('max_age')
        if min_age:
            queryset = queryset.filter(age_diagnosed__gte=min_age)
        if max_age:
            queryset = queryset.filter(age_diagnosed__lte=max_age)

        min_loading = self.request.query_params.get('min_loading')
        max_loading = self.request.query_params.get('max_loading')
        if min_loading:
            queryset = queryset.filter(premium_loading__gte=min_loading)
        if max_loading:
            queryset = queryset.filter(premium_loading__lte=max_loading)

        high_risk_only = self.request.query_params.get('high_risk_only')
        if high_risk_only and high_risk_only.lower() == 'true':
            queryset = queryset.filter(
                Q(condition_category__in=['cardiovascular', 'diabetes', 'cancer', 'neurological', 'genetic']) |
                Q(family_relation__in=['self', 'father', 'mother']) |
                Q(severity_level__in=['severe', 'critical'])
            )

        medical_exam_required = self.request.query_params.get('medical_exam_required')
        if medical_exam_required and medical_exam_required.lower() == 'true':
            queryset = queryset.filter(
                Q(condition_category__in=['cardiovascular', 'diabetes', 'cancer', 'neurological']) |
                Q(severity_level__in=['severe', 'critical']) |
                Q(family_relation='self')
            )

        checkup_from = self.request.query_params.get('checkup_from')
        checkup_to = self.request.query_params.get('checkup_to')
        if checkup_from:
            queryset = queryset.filter(last_checkup_date__gte=checkup_from)
        if checkup_to:
            queryset = queryset.filter(last_checkup_date__lte=checkup_to)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(condition_name__icontains=search) |
                Q(doctor_name__icontains=search) |
                Q(hospital_name__icontains=search) |
                Q(notes__icontains=search) |
                Q(current_medication__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__customer_code__icontains=search)
            )

        return queryset.select_related('customer').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='store')
    def store_customer_family_medical_history(self, request):
        try:
            serializer = CustomerFamilyMedicalHistoryCreateSerializer(data=request.data)
            if serializer.is_valid():
                medical_history = serializer.save(created_by=request.user)

                response_serializer = CustomerFamilyMedicalHistorySerializer(medical_history)
                return Response({
                    'success': True,
                    'message': 'Customer family medical history stored successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': 'Validation failed',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error storing customer family medical history: {str(e)}',
                'errors': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='list')
    def list_customer_family_medical_history(self, request):
        try:
            medical_history = CustomerFamilyMedicalHistory.objects.filter(is_deleted=False).select_related('customer').order_by('-created_at')

            customer_id = request.query_params.get('customer_id')
            if customer_id:
                medical_history = medical_history.filter(customer_id=customer_id)

            condition_category = request.query_params.get('condition_category')
            if condition_category:
                medical_history = medical_history.filter(condition_category=condition_category)

            condition_status = request.query_params.get('condition_status')
            if condition_status:
                medical_history = medical_history.filter(condition_status=condition_status)

            family_relation = request.query_params.get('family_relation')
            if family_relation:
                medical_history = medical_history.filter(family_relation=family_relation)

            severity_level = request.query_params.get('severity_level')
            if severity_level:
                medical_history = medical_history.filter(severity_level=severity_level)

            insurance_impact = request.query_params.get('insurance_impact')
            if insurance_impact:
                medical_history = medical_history.filter(insurance_impact=insurance_impact)

            is_active = request.query_params.get('is_active')
            if is_active is not None:
                medical_history = medical_history.filter(is_active=is_active.lower() == 'true')

            high_risk_only = request.query_params.get('high_risk_only')
            if high_risk_only and high_risk_only.lower() == 'true':
                medical_history = medical_history.filter(
                    Q(condition_category__in=['cardiovascular', 'diabetes', 'cancer', 'neurological', 'genetic']) |
                    Q(family_relation__in=['self', 'father', 'mother']) |
                    Q(severity_level__in=['severe', 'critical'])
                )

            # Search functionality
            search = request.query_params.get('search')
            if search:
                medical_history = medical_history.filter(
                    Q(condition_name__icontains=search) |
                    Q(doctor_name__icontains=search) |
                    Q(hospital_name__icontains=search) |
                    Q(notes__icontains=search) |
                    Q(current_medication__icontains=search) |
                    Q(customer__first_name__icontains=search) |
                    Q(customer__last_name__icontains=search) |
                    Q(customer__customer_code__icontains=search)
                )

            # Serialize the data
            serializer = CustomerFamilyMedicalHistoryListSerializer(medical_history, many=True)

            return Response({
                'success': True,
                'message': 'Customer family medical history retrieved successfully',
                'count': medical_history.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving customer family medical history: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
