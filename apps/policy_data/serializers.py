from rest_framework import serializers
from apps.files_upload.models import FileUpload
from apps.uploads.models import FileUpload as UploadsFileUpload
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.renewals.models import RenewalCase


class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = '__all__'


class EnhancedFileUploadSerializer(serializers.ModelSerializer):
    """Enhanced serializer for file upload with detailed processing info"""

    file_size_formatted = serializers.SerializerMethodField()
    processing_duration = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()

    class Meta:
        model = FileUpload
        fields = [
            'id', 'filename', 'original_filename', 'file_size', 'file_size_formatted',
            'file_type', 'upload_status', 'total_records', 'successful_records',
            'failed_records', 'uploaded_by', 'processing_started_at',
            'processing_completed_at', 'processing_duration', 'success_rate',
            'processing_result', 'error_details', 'created_at', 'upload_path'
        ]
        read_only_fields = [
            'id', 'filename', 'original_filename', 'file_size', 'file_type',
            'upload_status', 'total_records', 'successful_records', 'failed_records',
            'processing_started_at', 'processing_completed_at', 'processing_result',
            'error_details', 'created_at', 'upload_path'
        ]

    def get_file_size_formatted(self, obj):
        """Return human-readable file size"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def get_processing_duration(self, obj):
        """Calculate processing duration in seconds"""
        if obj.processing_started_at and obj.processing_completed_at:
            duration = obj.processing_completed_at - obj.processing_started_at
            return duration.total_seconds()
        return None

    def get_success_rate(self, obj):
        """Calculate success rate percentage"""
        if obj.total_records > 0:
            return round((obj.successful_records / obj.total_records) * 100, 2)
        return 0


class UploadsFileUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploads.FileUpload model"""

    file_extension = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()
    is_document = serializers.SerializerMethodField()
    formatted_size = serializers.SerializerMethodField()

    class Meta:
        model = UploadsFileUpload
        fields = [
            'id', 'original_name', 'file_size', 'formatted_size', 'mime_type',
            'file_hash', 'category', 'subcategory', 'tags', 'status',
            'processing_result', 'error_message', 'is_public', 'metadata',
            'description', 'download_count', 'last_accessed', 'expires_at',
            'created_at', 'updated_at', 'file_extension', 'is_image', 'is_document'
        ]
        read_only_fields = [
            'id', 'file_hash', 'download_count', 'last_accessed', 'created_at',
            'updated_at', 'file_extension', 'is_image', 'is_document', 'formatted_size'
        ]

    def get_file_extension(self, obj):
        """Get file extension"""
        return obj.file_extension

    def get_is_image(self, obj):
        """Check if file is an image"""
        return obj.is_image

    def get_is_document(self, obj):
        """Check if file is a document"""
        return obj.is_document

    def get_formatted_size(self, obj):
        """Get formatted file size"""
        return obj.formatted_size


class CustomerImportSerializer(serializers.ModelSerializer):
    """Serializer for customer data from Excel import"""

    full_name = serializers.SerializerMethodField()
    policies_count = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'customer_code', 'first_name', 'last_name',
            'full_name', 'email', 'phone', 'date_of_birth', 'gender',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country',
            'kyc_status', 'kyc_documents', 'communication_preferences',
            'status', 'priority', 'profile', 'policies_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'customer_code', 'full_name', 'profile', 'policies_count',
            'created_at', 'updated_at'
        ]

    def get_full_name(self, obj):
        """Get customer's full name"""
        return obj.full_name

    def get_policies_count(self, obj):
        """Get count of customer's policies"""
        return obj.total_policies


class PolicyImportSerializer(serializers.ModelSerializer):
    """Serializer for policy data from Excel import"""

    customer_name = serializers.SerializerMethodField()
    policy_type_name = serializers.SerializerMethodField()
    is_due_for_renewal = serializers.SerializerMethodField()

    class Meta:
        model = Policy
        fields = [
            'id', 'policy_number', 'customer', 'customer_name', 'policy_type',
            'policy_type_name', 'start_date', 'end_date', 'premium_amount',
            'sum_assured', 'status', 'nominee_name', 'nominee_relationship',
            'agent', 'is_due_for_renewal', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'customer_name', 'policy_type_name', 'is_due_for_renewal',
            'created_at', 'updated_at'
        ]

    def get_customer_name(self, obj):
        """Get customer's full name"""
        return obj.customer.full_name if obj.customer else None

    def get_policy_type_name(self, obj):
        """Get policy type name"""
        return obj.policy_type.name if obj.policy_type else None

    def get_is_due_for_renewal(self, obj):
        """Check if policy is due for renewal"""
        return obj.is_due_for_renewal


class RenewalCaseImportSerializer(serializers.ModelSerializer):
    """Serializer for renewal case data from Excel import"""

    customer_name = serializers.SerializerMethodField()
    customer_profile = serializers.SerializerMethodField()
    policy_number = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    channel_name = serializers.SerializerMethodField()

    class Meta:
        model = RenewalCase
        fields = [
            'id', 'case_number', 'batch_code', 'customer', 'customer_name', 'customer_profile', 'policy',
            'policy_number', 'status', 'priority', 'assigned_to', 'assigned_to_name',
            'renewal_amount', 'payment_status',
            'communication_attempts_count', 'last_contact_date', 'channel_id', 'channel_name', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'case_number', 'batch_code', 'customer_name', 'customer_profile', 'policy_number', 'assigned_to_name',
            'channel_name', 'created_at', 'updated_at'
        ]

    def get_customer_name(self, obj):
        """Get customer's full name"""
        return obj.customer.full_name if obj.customer else None

    def get_customer_profile(self, obj):
        """Get customer profile information"""
        if obj.customer:
            return {
                'id': obj.customer.id,
                'email': obj.customer.email,
                'phone': obj.customer.phone,
                'status': obj.customer.status,
            }
        return None

    def get_policy_number(self, obj):
        """Get policy number"""
        return obj.policy.policy_number if obj.policy else None

    def get_assigned_to_name(self, obj):
        """Get assigned user's full name"""
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()
        return None

    def get_channel_name(self, obj):
        """Get channel name"""
        return obj.customer.channel_id.name if obj.customer and obj.customer.channel_id else None


class FileProcessingStatusSerializer(serializers.Serializer):
    """Serializer for file processing status response"""

    file_upload_id = serializers.IntegerField()
    uploads_file_id = serializers.IntegerField()
    filename = serializers.CharField()
    status = serializers.CharField()
    total_records = serializers.IntegerField()
    successful_records = serializers.IntegerField()
    failed_records = serializers.IntegerField()
    success_rate = serializers.FloatField()
    processing_started_at = serializers.DateTimeField()
    processing_completed_at = serializers.DateTimeField(allow_null=True)
    processing_duration = serializers.FloatField(allow_null=True)
    errors = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    created_customers = serializers.IntegerField()
    created_policies = serializers.IntegerField()
    created_renewal_cases = serializers.IntegerField()


class ExcelValidationSerializer(serializers.Serializer):
    """Serializer for Excel file validation response"""

    valid = serializers.BooleanField()
    total_rows = serializers.IntegerField()
    total_columns = serializers.IntegerField()
    missing_columns = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    extra_columns = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    data_quality_issues = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    recommendations = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class FileUploadRequestSerializer(serializers.Serializer):
    """Serializer for file upload request"""

    file = serializers.FileField(
        help_text="Excel file (.xlsx or .xls) or CSV file (.csv) containing customer and policy data"
    )
    description = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Optional description for the file upload"
    )
    category = serializers.ChoiceField(
        choices=[
            ('customer_import', 'Customer Import'),
            ('policy_import', 'Policy Import'),
            ('renewal_import', 'Renewal Import'),
            ('bulk_import', 'Bulk Import'),
        ],
        default='bulk_import',
        help_text="Category of the import"
    )
    

    def validate_file(self, value):
        """Validate uploaded file"""

        allowed_extensions = ['.xlsx', '.xls', '.csv']
        file_extension = value.name.split('.')[-1].lower()
        if f'.{file_extension}' not in allowed_extensions:
            raise serializers.ValidationError(
                "File format not supported. Please upload a CSV (.csv) or Excel (.xlsx, .xls) file."
            )
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError(
                "File too large. Maximum size is 50MB."
            )

        return value
