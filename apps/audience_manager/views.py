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
    
    queryset = Audience.objects.none() # Use get_queryset for dynamic filtering
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AudienceCreateUpdateSerializer
        # For list, retrieve, etc.
        return AudienceSerializer
    
    def get_queryset(self):
        # Return all non-deleted audiences, ordered by last update
        return Audience.objects.filter(is_deleted=False).order_by('-last_updated')

    # --- Standard CRUD Operations ---

    def perform_create(self, serializer):
        """Sets created_by user on creation."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Updates last_updated time and implicitly sets updated_by (via model signal/middleware if configured)."""
        serializer.save(last_updated=timezone.now())

    def destroy(self, request, *args, **kwargs):
        """Performs soft delete."""
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        # Soft delete all associated contacts
        AudienceContact.objects.filter(audience=instance, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- Custom Actions for Contact Management ---

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """List contacts for a specific audience."""
        audience = self.get_object()
        contacts_queryset = audience.contacts.filter(is_deleted=False).order_by('name')
        
        # Simple list of contacts (no pagination needed based on video)
        serializer = AudienceContactSerializer(contacts_queryset, many=True)
        
        return Response({
            'audience_name': audience.name,
            'contact_count': contacts_queryset.count(),
            'contacts': serializer.data
        })

    @action(detail=True, methods=['post'], url_path='add-contacts')
    def add_contacts(self, request, pk=None):
        """Add one or more contacts manually or via bulk serializer."""
        audience = self.get_object()
        
        # Expects a list of contact dictionaries
        contacts_data = request.data.get('contacts', [])
        
        serializer = AudienceContactWriteSerializer(data=contacts_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Separate valid contacts from duplicates
        new_contacts = []
        for item in serializer.validated_data:
            # Check for existing email in this audience
            if not AudienceContact.objects.filter(audience=audience, email=item['email'], is_deleted=False).exists():
                new_contacts.append(
                    AudienceContact(
                        audience=audience,
                        created_by=request.user,
                        **item
                    )
                )
            # NOTE: For bulk, we ignore duplicates, but log them in a real app.

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
        """Handle contact bulk upload via CSV file."""
        audience = self.get_object()
        # --- Initial Validation ---
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES['file']

        # --- Duplicate File Check (moved after validation) ---
        hasher = hashlib.sha256()
        for chunk in file.chunks():
            hasher.update(chunk)
        file_hash = hasher.hexdigest()
        file.seek(0) # Reset file pointer after reading

        # Check if a file with this hash has been uploaded for this audience before
        if Audience.objects.filter(id=audience.id, metadata__uploaded_files__contains={file_hash: file.name}).exists():
            return Response({'error': f"Duplicate file. '{file.name}' has already been uploaded to this audience."}, status=status.HTTP_409_CONFLICT)
        # --- End Duplicate File Check ---
        
        try:
            # Decode the file and read it using the csv module
            decoded_file = file.read().decode('utf-8-sig') # Use utf-8-sig to handle BOM
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            contacts_data = [row for row in reader]
        except (UnicodeDecodeError, csv.Error) as e:
            return Response({'error': f"Error parsing CSV file: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AudienceContactWriteSerializer(data=contacts_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get existing emails to prevent duplicates
        existing_emails = set(AudienceContact.objects.filter(
            audience=audience, is_deleted=False
        ).values_list('email', flat=True))

        new_contacts = []
        for item in serializer.validated_data:
            if item['email'] not in existing_emails:
                new_contacts.append(AudienceContact(audience=audience, created_by=request.user, **item))
                existing_emails.add(item['email']) # Add to set to handle duplicates within the CSV

        if new_contacts:
            AudienceContact.objects.bulk_create(new_contacts)
            # Recalculate stats from the source of truth
            audience.contact_count = AudienceContact.objects.filter(audience=audience, is_deleted=False).count()
            audience.last_updated = timezone.now()
            audience.save()

            # Record the file hash in the audience's metadata to prevent re-upload
            if 'uploaded_files' not in audience.metadata:
                audience.metadata['uploaded_files'] = {}
            audience.metadata['uploaded_files'][file_hash] = file.name
            audience.save(update_fields=['metadata'])

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


class AudienceContactViewSet(viewsets.ModelViewSet):
    """ViewSet for managing individual AudienceContacts."""
    
    queryset = AudienceContact.objects.filter(is_deleted=False)
    serializer_class = AudienceContactSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        """Sets created_by user and updates audience count."""
        contact = serializer.save(created_by=self.request.user)
        # Update parent audience stats
        contact.audience.contact_count = contact.audience.contacts.filter(is_deleted=False).count()
        contact.audience.last_updated = timezone.now()
        contact.audience.save()

    def perform_destroy(self, instance: AudienceContact):
        """Performs soft delete and updates audience count."""
        audience = instance.audience
        instance.soft_delete(user=self.request.user)
        
        # Decrement parent audience stats
        audience.contact_count = AudienceContact.objects.filter(audience=audience, is_deleted=False).count()
        audience.last_updated = timezone.now()
        audience.save()