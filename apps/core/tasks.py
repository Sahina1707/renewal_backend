from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_email_task(self, subject, message, recipient_list, from_email=None):
    try:
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False
        )
        logger.info(f"Email sent successfully to {recipient_list}")
        return f"Email sent to {len(recipient_list)} recipients"
        
    except Exception as exc:
        logger.error(f"Error sending email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

@shared_task
def cleanup_expired_sessions():
    try:
        from apps.users.models import UserSession
        
        expired_sessions = UserSession.objects.filter(
            expires_at__lt=timezone.now()
        )
        count = expired_sessions.count()
        expired_sessions.delete()
        
        logger.info(f"Cleaned up {count} expired sessions")
        return f"Cleaned up {count} expired sessions"
        
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {str(e)}")
        raise

@shared_task
def cleanup_expired_password_reset_tokens():
    try:
        from apps.users.models import PasswordResetToken
        
        expired_tokens = PasswordResetToken.objects.filter(
            expires_at__lt=timezone.now()
        )
        count = expired_tokens.count()
        expired_tokens.delete()
        
        logger.info(f"Cleaned up {count} expired password reset tokens")
        return f"Cleaned up {count} expired tokens"
        
    except Exception as e:
        logger.error(f"Error cleaning up password reset tokens: {str(e)}")
        raise


@shared_task
def cleanup_old_audit_logs():
    try:
        from apps.core.models import AuditLog
        
        cutoff_date = timezone.now() - timedelta(days=365)
        old_logs = AuditLog.objects.filter(created_at__lt=cutoff_date)
        count = old_logs.count()
        old_logs.delete()
        
        logger.info(f"Cleaned up {count} old audit logs")
        return f"Cleaned up {count} old audit logs"
        
    except Exception as e:
        logger.error(f"Error cleaning up audit logs: {str(e)}")
        raise


@shared_task
def process_file_upload(file_id):
    try:
        from apps.uploads.models import FileUpload, FileProcessingQueue
        
        file_upload = FileUpload.objects.get(id=file_id)
        file_upload.status = 'processing'
        file_upload.save()
        
        tasks = []
        
        tasks.append(FileProcessingQueue.objects.create(
            file=file_upload,
            task_type='virus_scan',
            priority=1
        ))
        
        tasks.append(FileProcessingQueue.objects.create(
            file=file_upload,
            task_type='metadata_extract',
            priority=2
        ))
        
        if file_upload.is_image:
            tasks.append(FileProcessingQueue.objects.create(
                file=file_upload,
                task_type='thumbnail_generate',
                priority=3
            ))
        
        logger.info(f"Created {len(tasks)} processing tasks for file {file_id}")
        return f"Created {len(tasks)} processing tasks"
        
    except Exception as e:
        logger.error(f"Error processing file upload {file_id}: {str(e)}")
        try:
            file_upload = FileUpload.objects.get(id=file_id)
            file_upload.status = 'failed'
            file_upload.error_message = str(e)
            file_upload.save()
        except:
            pass
        raise


@shared_task
def update_customer_metrics():
    try:
        from apps.customers.models import Customer
        
        customers = Customer.objects.filter(is_deleted=False)
        updated_count = 0
        
        for customer in customers:
            customer.update_metrics()
            updated_count += 1
        
        logger.info(f"Updated metrics for {updated_count} customers")
        return f"Updated metrics for {updated_count} customers"
        
    except Exception as e:
        logger.error(f"Error updating customer metrics: {str(e)}")
        raise


@shared_task
def send_policy_renewal_reminders():
    try:
        from apps.policies.models import Policy
        from datetime import date
        
        reminder_date = date.today() + timedelta(days=30)
        expiring_policies = Policy.objects.filter(
            policy_end_date=reminder_date,
            status='active',
            is_deleted=False
        )
        
        sent_count = 0
        for policy in expiring_policies:
            send_email_task.delay(
                subject=f"Policy Renewal Reminder - {policy.policy_number}",
                message=f"Dear {policy.customer.full_name}, your policy {policy.policy_number} is expiring on {policy.policy_end_date}. Please contact us for renewal.",
                recipient_list=[policy.customer.email]
            )
            sent_count += 1
        
        logger.info(f"Sent renewal reminders for {sent_count} policies")
        return f"Sent {sent_count} renewal reminders"
        
    except Exception as e:
        logger.error(f"Error sending renewal reminders: {str(e)}")
        raise


@shared_task
def generate_daily_report():
    """
    Generate daily system report.
    """
    try:
        from apps.customers.models import Customer
        from apps.policies.models import Policy
        from apps.users.models import User
        
        today = timezone.now().date()
        
        stats = {
            'date': today.isoformat(),
            'customers': {
                'total': Customer.objects.filter(is_deleted=False).count(),
                'new_today': Customer.objects.filter(
                    created_at__date=today,
                    is_deleted=False
                ).count(),
                'active': Customer.objects.filter(
                    status='active',
                    is_deleted=False
                ).count(),
            },
            'policies': {
                'total': Policy.objects.filter(is_deleted=False).count(),
                'active': Policy.objects.filter(
                    status='active',
                    is_deleted=False
                ).count(),
                'expiring_soon': Policy.objects.filter(
                    policy_end_date__lte=today + timedelta(days=30),
                    status='active',
                    is_deleted=False
                ).count(),
            },
            'users': {
                'total': User.objects.filter(is_active=True).count(),
                'logged_in_today': User.objects.filter(
                    last_login__date=today
                ).count(),
            }
        }
        
        admin_emails = User.objects.filter(
            is_superuser=True,
            is_active=True
        ).values_list('email', flat=True)
        
        if admin_emails:
            report_content = f"""
            Daily System Report - {today}
            
            Customers:
            - Total: {stats['customers']['total']}
            - New Today: {stats['customers']['new_today']}
            - Active: {stats['customers']['active']}
            
            Policies:
            - Total: {stats['policies']['total']}
            - Active: {stats['policies']['active']}
            - Expiring Soon: {stats['policies']['expiring_soon']}
            
            Users:
            - Total: {stats['users']['total']}
            - Logged in Today: {stats['users']['logged_in_today']}
            """
            
            send_email_task.delay(
                subject=f"Daily System Report - {today}",
                message=report_content,
                recipient_list=list(admin_emails)
            )
        
        logger.info(f"Generated daily report for {today}")
        return f"Daily report generated and sent to {len(admin_emails)} administrators"
        
    except Exception as e:
        logger.error(f"Error generating daily report: {str(e)}")
        raise


@shared_task
def backup_database():
    """
    Create database backup (placeholder - implement based on your backup strategy).
    """
    try:
        logger.info("Database backup task executed (placeholder)")
        return "Database backup completed"
        
    except Exception as e:
        logger.error(f"Error creating database backup: {str(e)}")
        raise 