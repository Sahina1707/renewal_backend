from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging
import os

from .models import KnowledgeDocument, KnowledgeWebsite
from .services import KnowledgeService

logger = logging.getLogger(__name__)

# =================================================
# DOCUMENT OCR TASK (FINAL – SINGLE SOURCE OF TRUTH)
# =================================================
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def process_document_ocr(self, document_id):
    """
    Background OCR task.
    Flow:
    pending → processing → completed / failed
    """

    logger.info("OCR TASK STARTED (doc_id=%s)", document_id)

    try:
        # -------------------------------------------------
        # FETCH DOCUMENT
        # -------------------------------------------------
        doc = KnowledgeDocument.objects.get(id=document_id)
        logger.info(
            "Document loaded (status=%s, ocr_status=%s)",
            doc.status,
            doc.ocr_status,
        )

        # -------------------------------------------------
        # SAFETY CHECKS
        # -------------------------------------------------
        if doc.status != "approved":
            logger.warning(
                "⏭ OCR skipped: document not approved (id=%s)",
                document_id,
            )
            return

        if doc.ocr_status == "completed":
            logger.info(
                "⏭ OCR skipped: already completed (id=%s)",
                document_id,
            )
            return

        # -------------------------------------------------
        # SET OCR STATUS → PROCESSING
        # -------------------------------------------------
        with transaction.atomic():
            doc.ocr_status = "processing"
            doc.ocr_failure_reason = None
            doc.save(update_fields=["ocr_status", "ocr_failure_reason"])

        logger.info("OCR STATUS SET TO PROCESSING (id=%s)", document_id)

        # -------------------------------------------------
        # FILE PATH VALIDATION
        # -------------------------------------------------
        if not doc.document_file:
            raise Exception("No document file attached")

        file_path = doc.document_file.path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"OCR file not found: {file_path}")

        logger.info("OCR FILE PATH: %s", file_path)

        # -------------------------------------------------
        # OCR EXECUTION
        # -------------------------------------------------
        text, accuracy = KnowledgeService.extract_text_from_document(file_path)

        if not text or not text.strip():
            raise Exception("OCR completed but no text detected")

        # -------------------------------------------------
        # SAVE OCR RESULT
        # -------------------------------------------------
        doc.extracted_text = text
        doc.ocr_accuracy = accuracy
        doc.ocr_status = "completed"
        doc.save(
            update_fields=[
                "extracted_text",
                "ocr_accuracy",
                "ocr_status",
            ]
        )

        logger.info(
            "OCR COMPLETED (doc_id=%s, accuracy=%s)",
            document_id,
            accuracy,
        )

    except KnowledgeDocument.DoesNotExist:
        logger.error(
            "OCR FAILED: document not found (id=%s)",
            document_id,
        )
        return

    except Exception as exc:
        # -------------------------------------------------
        # MARK FAILURE PROPERLY (THIS WAS MISSING ❗)
        # -------------------------------------------------
        logger.exception(
            "OCR FAILED (doc_id=%s)",
            document_id,
        )

        try:
            doc.ocr_status = "failed"
            doc.ocr_failure_reason = str(exc)
            doc.save(update_fields=["ocr_status", "ocr_failure_reason"])
        except Exception:
            logger.error("Failed to update OCR failure status in DB")

        raise exc


# =================================================
# WEBSITE SCRAPING TASK (UPDATED – ATOMIC & UI-ALIGNED)
# =================================================

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def scrape_website(self, website_id):
    """
    Background website scraping task.
    Updates extracted_text, last_scraped_at,
    scraping_status, and failure reason.
    """

    logger.info("SCRAPE TASK STARTED (site_id=%s)", website_id)

    try:
        site = KnowledgeWebsite.objects.get(id=website_id)

        # -------------------------------------------------
        # SAFETY CHECKS (UNCHANGED)
        # -------------------------------------------------
        if site.is_deleted:
            logger.warning(
                "⏭ Scraping skipped: website deleted (id=%s)",
                website_id,
            )
            return

        if site.status != "active":
            logger.warning(
                "⏭ Scraping skipped: website inactive (id=%s)",
                website_id,
            )
            return

        # -------------------------------------------------
        # ATOMIC → SET STATUS = PROCESSING  (ADDED)
        # -------------------------------------------------
        with transaction.atomic():
            site.scraping_status = "processing"
            site.scraping_failure_reason = None
            site.save(
                update_fields=[
                    "scraping_status",
                    "scraping_failure_reason",
                ]
            )

        # -------------------------------------------------
        # SCRAPING LOGIC (STATIC FIRST – UI DRIVEN)
        # -------------------------------------------------
        if site.scraping_type == "static":
            extracted_text = KnowledgeService.scrape_static_website(
                site.url
            )
        else:
            # Dynamic scraping is intentionally restricted
            raise NotImplementedError(
                "Dynamic scraping is not implemented yet"
            )

        logger.info(
            "Scraped text length (site_id=%s): %s",
            website_id,
            len(extracted_text or ""),
        )

        # -------------------------------------------------
        # GUARD: DO NOT SAVE EMPTY CONTENT (UNCHANGED)
        # -------------------------------------------------
        if not extracted_text:
            raise Exception("Scraping returned empty content")

        # -------------------------------------------------
        # ATOMIC → SUCCESS COMMIT  (ADDED)
        # -------------------------------------------------
        with transaction.atomic():
            site.extracted_text = extracted_text
            site.last_scraped_at = timezone.now()
            site.scraping_status = "completed"
            site.save(
                update_fields=[
                    "extracted_text",
                    "last_scraped_at",
                    "scraping_status",
                ]
            )

        logger.info(
            "WEBSITE SCRAPED SUCCESSFULLY (site_id=%s)",
            website_id,
        )

    except KnowledgeWebsite.DoesNotExist:
        logger.error(
            "SCRAPING FAILED: website not found (id=%s)",
            website_id,
        )
        return

    except Exception as exc:
        # -------------------------------------------------
        # ATOMIC → FAILURE COMMIT  (ADDED)
        # -------------------------------------------------
        with transaction.atomic():
            site.scraping_status = "failed"
            site.scraping_failure_reason = str(exc)
            site.save(
                update_fields=[
                    "scraping_status",
                    "scraping_failure_reason",
                ]
            )

        logger.exception(
            "❌ SCRAPING FAILED (site_id=%s)",
            website_id,
        )
        raise exc

# =================================================
# SCHEDULED SCRAPING DISPATCHER (UI FREQUENCY)
# =================================================

@shared_task
def dispatch_scheduled_scraping():
    """
    Dispatch scraping tasks based on scraping_frequency
    """

    now = timezone.now()

    websites = KnowledgeWebsite.objects.filter(
        status="active",
        is_deleted=False,
    )

    for site in websites:
        # Skip if already running
        if site.scraping_status == "processing":
            continue

        # First-time scrape
        if not site.last_scraped_at:
            scrape_website.delay(site.id)
            continue

        delta = now - site.last_scraped_at

        if site.scraping_frequency == "hourly" and delta >= timedelta(hours=1):
            scrape_website.delay(site.id)

        elif site.scraping_frequency == "daily" and delta >= timedelta(days=1):
            scrape_website.delay(site.id)

        elif site.scraping_frequency == "weekly" and delta >= timedelta(weeks=1):
            scrape_website.delay(site.id)

        elif site.scraping_frequency == "monthly" and delta >= timedelta(days=30):
            scrape_website.delay(site.id)
