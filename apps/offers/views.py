from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.http import Http404
from decimal import Decimal
from .models import Offer
from .serializers import OfferSerializer, OfferCreateSerializer, OfferUpdateSerializer


class OfferViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing offers
    Provides CRUD operations for offers that are common to all customers
    """
    queryset = Offer.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['offer_type', 'is_active', 'currency']
    search_fields = ['title', 'description', 'features']
    ordering_fields = ['title', 'display_order', 'created_at', 'amount']
    ordering = ['display_order', 'created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return OfferCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OfferUpdateSerializer
        return OfferSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by active offers only if requested
        active_only = self.request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        # Filter by currently active offers (considering dates)
        currently_active = self.request.query_params.get('currently_active', 'false').lower() == 'true'
        if currently_active:
            from django.utils import timezone
            now = timezone.now()
            queryset = queryset.filter(
                is_active=True,
                start_date__lte=now,
                end_date__gte=now
            ).union(
                queryset.filter(
                    is_active=True,
                    start_date__isnull=True,
                    end_date__isnull=True
                )
            )
        
        return queryset
    
    @action(detail=False, methods=['get'], url_path='active-offers')
    def active_offers(self, request):
        """Get all currently active offers"""
        try:
            from django.utils import timezone
            now = timezone.now()
            
            # Get offers that are currently active
            offers = self.get_queryset().filter(
                is_active=True
            ).filter(
                Q(start_date__isnull=True) | Q(start_date__lte=now)
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            ).order_by('display_order', 'created_at')
            
            serializer = self.get_serializer(offers, many=True)
            return Response({
                'success': True,
                'message': 'Active offers retrieved successfully',
                'data': serializer.data,
                'count': offers.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving active offers: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='by-type/(?P<offer_type>[^/.]+)')
    def by_type(self, request, offer_type=None):
        """Get offers by type (payment_option, product, bundle, etc.)"""
        try:
            if not offer_type:
                return Response({
                    'success': False,
                    'message': 'Offer type parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate offer type
            valid_types = [choice[0] for choice in Offer.OFFER_TYPE_CHOICES]
            if offer_type not in valid_types:
                return Response({
                    'success': False,
                    'message': f'Invalid offer type. Must be one of: {", ".join(valid_types)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            offers = self.get_queryset().filter(offer_type=offer_type)
            serializer = self.get_serializer(offers, many=True)
            
            return Response({
                'success': True,
                'message': f'Offers for type "{offer_type}" retrieved successfully',
                'data': serializer.data,
                'count': offers.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving offers by type: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def create(self, request, *args, **kwargs):
        """Create a new offer"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response({
            'success': True,
            'message': 'Offer created successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Update an existing offer"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'success': True,
            'message': 'Offer updated successfully',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """Delete an offer (soft delete)"""
        instance = self.get_object()
        self.perform_destroy(instance)
        
        return Response({
            'success': True,
            'message': 'Offer deleted successfully',
            'data': None
        }, status=status.HTTP_204_NO_CONTENT)
    
    def list(self, request, *args, **kwargs):
        """List all offers with filtering and pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Offers retrieved successfully',
            'data': serializer.data,
            'count': queryset.count()
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='for-case/(?P<case_id>[^/.]+)')
    def for_case(self, request, case_id=None):
        """Get offers filtered by customer eligibility based on case_id"""
        try:
            from apps.renewals.models import RenewalCase
            
            # Get renewal case by case_number
            try:
                renewal_case = RenewalCase.objects.select_related(
                    'customer', 
                    'customer__financial_profile'
                ).get(case_number=case_id)
            except RenewalCase.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Case with ID {case_id} not found',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)
            
            customer = renewal_case.customer
            
            # Get customer financial profile
            financial_profile = None
            annual_income = None
            try:
                financial_profile = customer.financial_profile
                if financial_profile and financial_profile.annual_income:
                    annual_income = float(financial_profile.annual_income)
            except Exception:
                pass
            
            # Get customer assets
            from apps.customer_assets.models import CustomerAssets
            has_assets = CustomerAssets.objects.filter(
                customer=customer,
                is_deleted=False
            ).exists()
            
            # Get all active offers
            all_offers = Offer.objects.filter(is_active=True).order_by('display_order')
            
            # Filter offers based on eligibility
            eligible_offers = []
            
            for offer in all_offers:
                is_eligible = False
                offer_title_lower = offer.title.lower()
                offer_type = offer.offer_type
                
                # EMI Payment Plan - Everyone eligible
                if offer_title_lower == 'emi payment plan':
                    is_eligible = True
                
                # Quarterly Payment - Income > ₹5,00,000
                elif offer_title_lower == 'quarterly payment':
                    if annual_income and annual_income > 500000:
                        is_eligible = True
                
                # Annual Payment - Income > ₹8,00,000
                elif offer_title_lower == 'annual payment':
                    if annual_income and annual_income > 800000:
                        is_eligible = True
                
                # Premium Funding - Customer has assets (or existing loan if available)
                elif offer_title_lower == 'premium funding':
                    if has_assets:
                        is_eligible = True
                    # Note: If you have a loan field in financial_profile, add it here
                    # elif financial_profile and financial_profile.has_existing_loan:
                    #     is_eligible = True
                
                # Product and Bundle offers - Only show if customer has reasonable income
                # Income threshold: ₹3,00,000 (assets alone are not enough)
                elif offer_type in ['product', 'bundle']:
                    if annual_income and annual_income > 300000:
                        is_eligible = True
                
                # Discount and Special Offer - Only show if customer has reasonable income
                # Income threshold: ₹3,00,000 (assets alone are not enough)
                elif offer_type in ['discount', 'special_offer']:
                    if annual_income and annual_income > 300000:
                        is_eligible = True
                
                # For any other offer types, don't show by default (strict filtering)
                # If you want to show other types, add specific conditions above
                
                if is_eligible:
                    eligible_offers.append(offer)
            
            serializer = self.get_serializer(eligible_offers, many=True)
            
            return Response({
                'success': True,
                'message': f'Offers retrieved successfully for case {case_id}',
                'data': serializer.data,
                'count': len(eligible_offers)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving offers: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)