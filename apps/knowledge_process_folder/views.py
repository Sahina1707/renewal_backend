from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction

import logging

from .models import KnowledgeDocument, KnowledgeWebsite, DocumentModule
from .serializers import (
    KnowledgeDocumentSerializer,
    KnowledgeDocumentViewDetailsSerializer,
    KnowledgeWebsiteSerializer,
    DocumentModuleSerializer,
)
from .tasks import process_document_ocr, scrape_website


logger = logging.getLogger(__name__)


# ======================================================
# DOCUMENT MODULE VIEWSET (UPDATED – POST + GET ENABLED)
# ======================================================
class DocumentModuleViewSet(ModelViewSet):
    """
    Handles:
    - POST   → Add new document module
    - GET    → List all modules
    - GET ID → Retrieve single module

    Used for dynamic module selection across the system.
    """

    queryset = DocumentModule.objects.filter(is_active=True)
    serializer_class = DocumentModuleSerializer
    permission_classes = [IsAuthenticated]


# ======================================================
# KNOWLEDGE DOCUMENT VIEWSET
# ======================================================
class KnowledgeDocumentViewSet(ModelViewSet):
    """
    Handles:
    - Upload document
    - List documents
    - Approve document
    - Reject document
    - Soft delete document

    Enterprise rules:
    - Superuser sees all records (including deleted)
    - Normal users see only non-deleted records
    """

    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [IsAuthenticated]

    # --------------------------------------------------
    # QUERYSET ACCESS CONTROL (CRITICAL)
    # --------------------------------------------------
    def get_queryset(self):
        qs = KnowledgeDocument.objects.all().order_by("-uploaded_at")

        if self.request.user.is_superuser:
            return qs

        return qs.filter(is_deleted=False)

    # --------------------------------------------------
    # UPLOAD DOCUMENT
    # --------------------------------------------------
    def perform_create(self, serializer):
        serializer.save(
            uploaded_by=self.request.user,
            status="pending",
            ocr_status="pending",
        )

    # --------------------------------------------------
    # APPROVE DOCUMENT
    # --------------------------------------------------
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        doc = get_object_or_404(
            KnowledgeDocument,
            pk=pk,
            is_deleted=False,
        )

        if doc.status == "approved":
            return Response(
                {"message": "Document already approved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            doc.status = "approved"
            doc.approved_by = request.user
            doc.approved_at = timezone.now()
            doc.save(update_fields=["status", "approved_by", "approved_at"])

            def trigger_ocr():
                try:
                    process_document_ocr.delay(doc.id)
                except Exception as exc:
                    logger.error(
                        "OCR enqueue failed for document %s: %s",
                        doc.id,
                        str(exc),
                    )

            transaction.on_commit(trigger_ocr)

        return Response(
            {
                "message": "Document approved successfully",
                "note": "OCR will run in background if worker is available",
            },
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------
    # REJECT DOCUMENT
    # --------------------------------------------------
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        doc = get_object_or_404(
            KnowledgeDocument,
            pk=pk,
            is_deleted=False,
        )

        if doc.status == "rejected":
            return Response(
                {"message": "Document already rejected"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc.status = "rejected"
        doc.rejection_reason = request.data.get("reason")
        doc.rejected_by = request.user
        doc.rejected_at = timezone.now()
        doc.save(
            update_fields=[
                "status",
                "rejection_reason",
                "rejected_by",
                "rejected_at",
            ]
        )

        return Response(
            {"message": "Document rejected successfully"},
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------
    # SOFT DELETE DOCUMENT
    # --------------------------------------------------
    @action(detail=True, methods=["delete"])
    def soft_delete(self, request, pk=None):
        document = self.get_object()
        document.deleted_by = request.user
        document.status = "DELETED"
        document.save(update_fields=["deleted_by", "status"])
        return Response({"message": "Document deleted successfully"})
    

    # --------------------------------------------------
    # VIEW DOCUMENT DETAILS (UI MODAL)
    # --------------------------------------------------
    @action(detail=True, methods=["get"], url_path="view-details")
    def view_details(self, request, pk=None):
        """
        Returns document details for View Details modal.
        Read-only endpoint.
        """
        document = get_object_or_404(
            KnowledgeDocument,
            pk=pk,
            is_deleted=False,
        )

        serializer = KnowledgeDocumentViewDetailsSerializer(document)

        return Response(
            {
                "success": True,
                "data": serializer.data
            },
            status=status.HTTP_200_OK,
        )



# ======================================================
# KNOWLEDGE WEBSITE VIEWSET
# ======================================================
class KnowledgeWebsiteViewSet(ModelViewSet):
    """
    Handles:
    - Add website
    - List websites
    - Scrape now
    - Soft delete website
    """

    serializer_class = KnowledgeWebsiteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = KnowledgeWebsite.objects.all().order_by("-created_at")

        if self.request.user.is_superuser:
            return qs

        return qs.filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(
            added_by=self.request.user,
            status="active",
        )

    @action(detail=True, methods=["post"])
    def scrape_now(self, request, pk=None):
        website = get_object_or_404(
            KnowledgeWebsite,
            pk=pk,
            is_deleted=False,
        )

        if website.status != "active":
            return Response(
                {"message": "Website is inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            scrape_website.delay(website.id)
        except Exception as exc:
            logger.error(
                "Website scrape enqueue failed for website %s: %s",
                website.id,
                str(exc),
            )

        return Response(
            {"message": "Website scraping triggered"},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
        return Response(status=status.HTTP_204_NO_CONTENT)
