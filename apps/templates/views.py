from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q,Sum
from django.shortcuts import get_object_or_404
from .models import Template
from .serializers import TemplateSerializer, TemplateCreateSerializer, TemplateUpdateSerializer
from apps.whatsapp_provider.models import WhatsAppProvider


class TemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for Template model"""
    
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action"""
        if self.action == 'create':
            return TemplateCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TemplateUpdateSerializer
        return TemplateSerializer
    
    def get_queryset(self):
        """Filter templates based on query parameters"""
        queryset = Template.objects.all()
        
        channel = self.request.query_params.get('channel', None)
        if channel:
            queryset = queryset.filter(channel=channel)
            
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
            
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
            
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(subject__icontains=search) |
                Q(content__icontains=search)
            )
            
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set the created_by field to the current user"""
        serializer.save(created_by=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create a new template"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {'message': 'Template created successfully'},
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    def update(self, request, *args, **kwargs):
        """Update a template"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'success': True,
            'message': 'Template updated successfully',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """Delete a template"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'success': True,
            'message': 'Template deleted successfully',
            'data': None
        }, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def get_all_templates(self, request):
        """Get all templates with optional filtering"""
        try:
            templates = self.get_queryset()
            serializer = self.get_serializer(templates, many=True)
            
            return Response({
                'success': True,
                'message': 'Templates retrieved successfully',
                'data': serializer.data,
                'count': templates.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving templates: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_templates_by_channel(self, request):
        """Get templates filtered by channel"""
        channel = request.query_params.get('channel')
        if not channel:
            return Response({
                'success': False,
                'message': 'Channel parameter is required',
                'data': []
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            templates = Template.objects.filter(channel=channel, is_active=True)
            serializer = self.get_serializer(templates, many=True)
            
            return Response({
                'success': True,
                'message': f'Templates for channel {channel} retrieved successfully',
                'data': serializer.data,
                'count': templates.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving templates: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate an existing template"""
        try:
            original_template = self.get_object()
            
            new_name = f"{original_template.name} (Copy)"
            counter = 1
            while Template.objects.filter(name=new_name).exists():
                new_name = f"{original_template.name} (Copy {counter})"
                counter += 1
            
            new_template = Template.objects.create(
                name=new_name,
                template_type=original_template.template_type,
                channel=original_template.channel,
                category=original_template.category,
                subject=original_template.subject,
                content=original_template.content,
                variables=original_template.variables,
                dlt_template_id=original_template.dlt_template_id,
                tags=list(original_template.tags) if isinstance(original_template.tags, list) else [],
                is_dlt_approved=original_template.is_dlt_approved,
                is_active=False,  
                created_by=request.user
            )
            
            serializer = self.get_serializer(new_template)
            return Response({
                'success': True,
                'message': 'Template duplicated successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error duplicating template: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle template active status"""
        try:
            template = self.get_object()
            template.is_active = not template.is_active
            template.save()
            
            serializer = self.get_serializer(template)
            status_text = "activated" if template.is_active else "deactivated"
            
            return Response({
                'success': True,
                'message': f'Template {status_text} successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error toggling template status: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get all available template categories"""
        try:
            categories = [{'value': choice[0], 'label': choice[1]} for choice in Template.CATEGORY_CHOICES]
            return Response({
                'success': True,
                'message': 'Categories retrieved successfully',
                'data': categories
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving categories: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def channels(self, request):
        """Get all available template channels"""
        try:
            channels = [{'value': choice[0], 'label': choice[1]} for choice in Template.TEMPLATE_TYPES]
            return Response({
                'success': True,
                'message': 'Channels retrieved successfully',
                'data': channels
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving channels: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def template_types(self, request):
        """Get all available template types"""
        try:
            template_types = [{'value': choice[0], 'label': choice[1]} for choice in Template.TEMPLATE_TYPE_CHOICES]
            return Response({
                'success': True,
                'message': 'Template types retrieved successfully',
                'data': template_types
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving template types: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # In views.py, inside TemplateViewSet
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get all available template stats"""
        try:
            total_templates = self.get_queryset().count()
            active_templates = self.get_queryset().filter(is_active=True).count()
            dlt_approved = self.get_queryset().filter(is_dlt_approved=True).count()
            total_usage = self.get_queryset().aggregate(Sum('usage_count'))['usage_count__sum'] or 0

            stats_data = {
            'total_templates': total_templates,
            'active_templates': active_templates,
            'dlt_approved': dlt_approved,
            'total_usage': total_usage
        }

            return Response({
            'success': True,
            'message': 'Stats retrieved successfully',
            'data': stats_data
        }, status=status.HTTP_200_OK)

        except Exception as e:
            # apps/whatsapp_provider/serializers.py
            
            from rest_framework import serializers
            from .models import WhatsAppProvider
            
            class WhatsAppProviderCreateUpdateSerializer(serializers.ModelSerializer):
                class Meta:
                    model = WhatsAppProvider
                    # Add 'meta_api_version' to the list of fields
                    fields = [
                        'name', 
                        'phone_number_id', 
                        'access_token', 
                        'meta_api_version',  # Add the missing field here
                        # ... other fields ...
                        'is_active',
                    ]
            
            return Response({
            'success': False,
            'message': f'Error retrieving stats: {str(e)}',
            'data': None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
