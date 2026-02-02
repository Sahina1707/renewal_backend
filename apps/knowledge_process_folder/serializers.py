from rest_framework import serializers
from .models import KnowledgeDocument, KnowledgeWebsite, DocumentModule
from django.utils import timezone


# ======================================================
# DOCUMENT MODULE SERIALIZER (ADDED)
# ======================================================
class DocumentModuleSerializer(serializers.ModelSerializer):
    """
    Serializer for document modules.
    Used to expose dynamic module list to frontend.
    """

    class Meta:
        model = DocumentModule
        fields = ["id", "name"]


# ======================================================
# KNOWLEDGE DOCUMENT SERIALIZER (UPDATED – FINAL)
# ======================================================
class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer aligned with UI + enterprise audit needs.
    """

    # -------- UI Friendly Fields --------
    uploaded_by = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    rejected_by = serializers.SerializerMethodField()
    deleted_by = serializers.SerializerMethodField()

    uploaded_at = serializers.DateTimeField(format="%Y-%m-%d", read_only=True)
    approved_at = serializers.DateTimeField(format="%Y-%m-%d", read_only=True)
    rejected_at = serializers.DateTimeField(format="%Y-%m-%d", read_only=True)

    # -------- Read-only System Fields --------
    document_type = serializers.CharField(read_only=True)
    document_size = serializers.SerializerMethodField()

    status = serializers.CharField(read_only=True)
    ocr_status = serializers.CharField(read_only=True)
    ocr_accuracy = serializers.FloatField(read_only=True)
    ocr_failure_reason = serializers.CharField(read_only=True)

    rejection_reason = serializers.CharField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)

    # ==================================================
    # EXPIRY VISIBILITY FIELDS
    # ==================================================
    is_expired = serializers.SerializerMethodField()
    expiry_display = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            "id",
            "document_name",
            "document_file",
            "document_type",
            "document_size",
            "modules",
            "expiry_date",

            # Expiry helpers
            "expiry_display",
            "is_expired",

            # Status & OCR
            "status",
            "ocr_status",
            "ocr_accuracy",
            "ocr_failure_reason",

            # Audit
            "uploaded_by",
            "uploaded_at",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "deleted_by",
            "is_deleted",
        ]

    # --------------------------------------------------
    # Helper methods for UI
    # --------------------------------------------------
    def get_document_size(self, obj):
        """
        Returns human-readable file size:
        B, KB, MB, GB
        """
        if not obj.document_file:
            return None

        size = obj.document_file.size

        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024

        return f"{size:.1f} PB"

    def get_uploaded_by(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.email
        return None

    def get_approved_by(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return None

    def get_rejected_by(self, obj):
        if obj.rejected_by:
            return obj.rejected_by.get_full_name() or obj.rejected_by.email
        return None

    def get_deleted_by(self, obj):
        if obj.deleted_by:
            return obj.deleted_by.get_full_name() or obj.deleted_by.email
        return None

    # ==================================================
    # EXPIRY LOGIC (USES MODEL PROPERTY)
    # ==================================================
    def get_is_expired(self, obj):
        return obj.is_expired

    def get_expiry_display(self, obj):
        if obj.is_expired:
            return "Expired"
        return obj.expiry_date

    # ==================================================
    # MODULE VALIDATION (IMPORTANT)
    # ==================================================
    def validate_modules(self, value):
        """
        Ensures only valid and active document modules are saved.
        Supports single or multiple modules.
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("Modules must be a list")

        valid_modules = set(
            DocumentModule.objects.filter(is_active=True)
            .values_list("name", flat=True)
        )

        invalid = set(value) - valid_modules
        if invalid:
            raise serializers.ValidationError(
                f"Invalid modules selected: {', '.join(invalid)}"
            )

        return value



# ======================================================
# KNOWLEDGE WEBSITE SERIALIZER (UPDATED – FIXED)
# ======================================================
class KnowledgeWebsiteSerializer(serializers.ModelSerializer):
    """
    Serializer aligned with Website list & modal UI.
    """

    added_by = serializers.SerializerMethodField()

    # FIX: DateTimeField instead of DateField
    added_at = serializers.DateTimeField(
        source="created_at",
        format="%Y-%m-%d",
        read_only=True
    )

    last_scraped_at = serializers.DateTimeField(
        format="%Y-%m-%d",
        read_only=True
    )

    class Meta:
        model = KnowledgeWebsite
        fields = [
            "id",
            "name",
            "url",
            "scraping_type",
            "scraping_frequency",
            "last_scraped_at",
            "status",
            "added_by",
            "added_at",
        ]

        read_only_fields = [
            "last_scraped_at",
            "status",
        ]

    def get_added_by(self, obj):
        if obj.added_by:
            return obj.added_by.get_full_name() or obj.added_by.email
        return None
    

# ======================================================
# KNOWLEDGE DOCUMENT – VIEW DETAILS SERIALIZER (ADDED)
# ======================================================
class KnowledgeDocumentViewDetailsSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.SerializerMethodField()
    upload_date = serializers.SerializerMethodField()

    document_type_display = serializers.SerializerMethodField()
    document_size_display = serializers.SerializerMethodField()

    preview_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            "id",
            "document_name",
            "document_type_display",
            "document_size_display",
            "uploaded_by",
            "upload_date",
            "ocr_status",
            "modules",
            "preview_url",
            "download_url",
        ]

    # -----------------------------
    # SAFE FIELD CONVERSIONS
    # -----------------------------
    def get_upload_date(self, obj):
        if obj.uploaded_at:
            return obj.uploaded_at.date()  # datetime → date (SAFE)
        return None

    def get_uploaded_by(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.email
        return None

    def get_document_type_display(self, obj):
        return (obj.document_type or "").upper()

    def get_document_size_display(self, obj):
        size = obj.document_size or 0
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def get_preview_url(self, obj):
        return obj.document_file.url if obj.document_file else None

    def get_download_url(self, obj):
        return obj.document_file.url if obj.document_file else None
