from rest_framework import serializers
from .models import CustomerFile
from apps.customers.models import Customer


class CustomerFileSerializer(serializers.ModelSerializer):
    """Serializer for CustomerFile model"""

    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    customer_name = serializers.CharField(read_only=True)
    customer_id = serializers.IntegerField(write_only=True)
    file = serializers.FileField(write_only=True, required=False)
    pan_number = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = CustomerFile
        fields = [
            'id', 'customer_id', 'customer', 'customer_name', 'file_name', 'file_path', 'file_type',
            'file_size', 'file_size_display', 'uploaded_by', 'uploaded_by_name',
            'uploaded_at', 'updated_by', 'updated_by_name', 'updated_at', 'is_active', 'file', 'pan_number'
        ]
        read_only_fields = ['id', 'uploaded_at', 'updated_at', 'customer', 'file_size']
        extra_kwargs = {
            'file_name': {'required': False, 'allow_blank': True},
            'file_path': {'required': False, 'allow_blank': True},
            'file_type': {'required': False, 'allow_blank': True},
        }

    def validate(self, data):
        """Validate that either file is uploaded or required fields are provided"""
        uploaded_file = data.get('file')

        if not uploaded_file:
            required_fields = ['file_name', 'file_path']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                raise serializers.ValidationError(
                    f"When not uploading a file, these fields are required: {', '.join(missing_fields)}"
                )

        return data

    def validate_customer_id(self, value):
        """Validate that the customer exists"""
        from apps.customers.models import Customer
        try:
            Customer.objects.get(id=value)
        except Customer.DoesNotExist:
            raise serializers.ValidationError("Customer with this ID does not exist.")
        return value

    def validate_file_name(self, value):
        """Validate file name if provided"""
        if value and not value.strip():
            raise serializers.ValidationError("File name cannot be empty.")
        return value.strip() if value else value

    def create(self, validated_data):
        """Custom create method to handle file upload and auto-detection"""
        import os
        import mimetypes
        import tempfile
        import logging
        from apps.customers.models import Customer
        from apps.verification.ocr_utils import extract_pan_from_image

        logger = logging.getLogger(__name__)
        
        customer_id = validated_data.pop('customer_id')
        customer = Customer.objects.get(id=customer_id)
        validated_data['customer'] = customer

        validated_data['is_active'] = True

        uploaded_file = validated_data.pop('file', None)
        temp_file_path = None
        
        if uploaded_file:
            validated_data['file_size'] = uploaded_file.size

            if not validated_data.get('file_name'):
                validated_data['file_name'] = uploaded_file.name

            if not validated_data.get('file_type'):
                if hasattr(uploaded_file, 'content_type') and uploaded_file.content_type:
                    validated_data['file_type'] = uploaded_file.content_type
                else:
                    file_type, _ = mimetypes.guess_type(uploaded_file.name)
                    validated_data['file_type'] = file_type or 'application/octet-stream'

            if not validated_data.get('file_path'):
                import uuid
                file_extension = os.path.splitext(uploaded_file.name)[1]
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                validated_data['file_path'] = f"/uploads/documents/{unique_filename}"
            
            file_type = validated_data.get('file_type', '')
            if not validated_data.get('pan_number') and file_type and 'image' in file_type.lower():
                try:
                    file_extension = os.path.splitext(uploaded_file.name)[1]
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
                    temp_file_path = temp_file.name
                    
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    temp_file.close()
                    
                    logger.info(f"Processing image for PAN extraction: {temp_file_path}")
                    
                    result = extract_pan_from_image(temp_file_path)
                    
                    if result.get('success') and result.get('pan_number'):
                        validated_data['pan_number'] = result['pan_number']
                        logger.info(f"PAN number extracted successfully: {result['pan_number']}")
                    else:
                        logger.info(f"PAN extraction failed: {result.get('message')}")
                        
                except Exception as e:
                    logger.error(f"Error during PAN extraction: {str(e)}")
                finally:
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except Exception as e:
                            logger.warning(f"Failed to delete temp file: {str(e)}")
        else:
            if not validated_data.get('file_type'):
                file_name = validated_data.get('file_name', '')
                if file_name:
                    file_type, _ = mimetypes.guess_type(file_name)
                    validated_data['file_type'] = file_type or 'application/octet-stream'
                else:
                    validated_data['file_type'] = 'application/octet-stream'

            if 'file_size' not in validated_data:
                validated_data['file_size'] = 0

        return super().create(validated_data)


class CustomerFileListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing customer files"""

    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    customer_name = serializers.CharField(read_only=True)
    customer_id = serializers.IntegerField(source='customer.id', read_only=True)

    class Meta:
        model = CustomerFile
        fields = [
            'id', 'customer_id', 'customer_name', 'file_name', 'file_type',
            'file_size_display', 'uploaded_at', 'is_active', 'pan_number'
        ]
