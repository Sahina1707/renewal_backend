from rest_framework import viewsets, status
from rest_framework.decorators import action, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Count, Q
from django.utils import timezone
import csv
import io
import hashlib

from .models import Audience, AudienceContact
from .serializers import (
    AudienceSerializer, AudienceCreateUpdateSerializer,
    AudienceContactSerializer, AudienceContactWriteSerializer
)


class AudienceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Audiences and their contacts."""
    
    queryset = Audience.objects.none() 
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AudienceCreateUpdateSerializer
        return AudienceSerializer
    
    def get_queryset(self):
        return Audience.objects.filter(is_deleted=False).order_by('-last_updated')

    # ... (Your other views: create, update, destroy, contacts) ...
    # ... (No changes needed to those) ...

    @action(detail=True, methods=['post'], url_path='add-contacts')
    def add_contacts(self, request, pk=None):
        """
        Add one or more contacts manually.
        Handles both a single object (dict) and a list of objects (list).
        Now validates against duplicate emails AND phone numbers.
        """
        audience = self.get_object()
        
        contacts_data = request.data
        is_many = isinstance(contacts_data, list)
        
        serializer = AudienceContactWriteSerializer(data=contacts_data, many=is_many)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        if not is_many:
            validated_data = [validated_data]

        # --- THIS IS THE UPDATE ---
        
        # 1. Get existing emails AND phones for this audience
        existing_emails = set(AudienceContact.objects.filter(
            audience=audience, is_deleted=False, email__isnull=False
        ).values_list('email', flat=True))
        
        existing_phones = set(AudienceContact.objects.filter(
            audience=audience, is_deleted=False, phone__isnull=False
        ).values_list('phone', flat=True))
        
        new_contacts = []
        for item in validated_data:
            email = item.get('email')
            phone = item.get('phone')
            if email:
                item['email'] = email.strip() # <--- ADDED!
            if phone:
                item['phone'] = phone.strip()
            email = item['email']
            phone = item['phone']
            
            # 2. Check for duplicates
            is_duplicate = False
            if email and email in existing_emails:
                is_duplicate = True
            
            if phone and phone in existing_phones:
                is_duplicate = True

            # 3. If not a duplicate, add to batch
            if not is_duplicate:
                new_contacts.append(
                    AudienceContact(
                        audience=audience,
                        created_by=request.user,
                        **item
                    )
                )
                # Add to sets to prevent duplicates within the same request
                if email:
                    existing_emails.add(email)
                if phone:
                    existing_phones.add(phone)
        
        # --- END UPDATE ---

        if new_contacts:
            AudienceContact.objects.bulk_create(new_contacts)
            # Update audience stats
            audience.contact_count = audience.contacts.filter(is_deleted=False).count()
            audience.last_updated = timezone.now()
            audience.save()
            
            return Response({
                'success': True,
                'message': f"Added {len(new_contacts)} new contacts to {audience.name}.",
                'added_count': len(new_contacts)
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': True,
            'message': 'No new contacts added (all contacts already exist or data was empty).'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='upload-contacts')
    @parser_classes([MultiPartParser, FormParser])
    def upload_contacts(self, request, pk=None):
        """
        Handle contact bulk upload via CSV file.
        Also updated to check both email and phone.
        """
        audience = self.get_object()
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES['file']
        
        # ... (Your file hash check logic is good) ...
        hasher = hashlib.sha256()
        for chunk in file.chunks():
            hasher.update(chunk)
        file_hash = hasher.hexdigest()
        file.seek(0)
        if Audience.objects.filter(id=audience.id, metadata__uploaded_files__contains={file_hash: file.name}).exists():
            return Response({'error': f"Duplicate file. '{file.name}' has already been uploaded."}, status=status.HTTP_409_CONFLICT)
        
        try:
            decoded_file = file.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            contacts_data = [row for row in reader]
        except (UnicodeDecodeError, csv.Error) as e:
            return Response({'error': f"Error parsing CSV file: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AudienceContactWriteSerializer(data=contacts_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # --- UPDATE: Get existing emails AND phones ---
        existing_emails = set(AudienceContact.objects.filter(
            audience=audience, is_deleted=False, email__isnull=False
        ).values_list('email', flat=True))
        
        existing_phones = set(AudienceContact.objects.filter(
            audience=audience, is_deleted=False, phone__isnull=False
        ).values_list('phone', flat=True))

        new_contacts = []
        for item in serializer.validated_data:
            email = item.get('email')
            phone = item.get('phone')
            if email:
                item['email'] = email.strip() # <--- ADDED!
                email = item['email']         # Use the cleaned value
            if phone:
                item['phone'] = phone.strip() # <--- OPTIONAL BUT RECOMMENDED!
                phone = item['phone']
            
            is_duplicate = False
            if email and email in existing_emails:
                is_duplicate = True
            if phone and phone in existing_phones:
                is_duplicate = True

            if not is_duplicate:
                new_contacts.append(AudienceContact(audience=audience, created_by=request.user, **item))
                if email:
                    existing_emails.add(email)
                if phone:
                    existing_phones.add(phone)
        # --- END UPDATE ---

        if new_contacts:
            AudienceContact.objects.bulk_create(new_contacts, ignore_conflicts=True)
            
            audience.contact_count = AudienceContact.objects.filter(audience=audience, is_deleted=False).count()
            audience.last_updated = timezone.now()
            
            if 'uploaded_files' not in audience.metadata:
                audience.metadata['uploaded_files'] = {}
            audience.metadata['uploaded_files'][file_hash] = file.name
            audience.save(update_fields=['contact_count', 'last_updated', 'metadata']) # Save all fields in one go

            return Response({
                'success': True,
                'message': f"Successfully added {len(new_contacts)} new contacts to '{audience.name}'.",
                'added_count': len(new_contacts),
                'duplicates_ignored': len(contacts_data) - len(new_contacts)
            }, status=status.HTTP_201_CREATED)

        return Response({
            'success': True,
            'message': 'No new contacts were added. They may already exist in the audience or the file was empty.'
        }, status=status.HTTP_200_OK)
    # Inside AudienceViewSet

    def perform_destroy(self, instance):
        """
        Soft delete the Audience instead of removing it from DB.
        """
        if hasattr(instance, 'soft_delete'):
            instance.soft_delete(user=self.request.user)
        else:
            # Fallback if specific method doesn't exist
            instance.is_deleted = True
            instance.metadata['deleted_by'] = self.request.user.id
            instance.metadata['deleted_at'] = str(timezone.now())
            instance.save()

class AudienceContactViewSet(viewsets.ModelViewSet):
    """ViewSet for managing individual AudienceContacts."""
    
    queryset = AudienceContact.objects.filter(is_deleted=False)
    serializer_class = AudienceContactSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        contact = serializer.save(created_by=self.request.user)
        # Update stats helper
        self._update_audience_stats(contact.audience)

    def perform_destroy(self, instance):
        """
        Soft delete the contact explicitly.
        This fixes the Foreign Key Constraint error immediately.
        """
        instance.is_deleted = True
        instance.save()
        
        self._update_audience_stats(instance.audience)

    def _update_audience_stats(self, audience):
        """Helper to update counts on the parent audience"""
        audience.contact_count = AudienceContact.objects.filter(
            audience=audience, 
            is_deleted=False
        ).count()
        audience.last_updated = timezone.now()
        audience.save(update_fields=['contact_count', 'last_updated'])