"""
Celery configuration for Intelipro Insurance Policy Renewal System.
"""
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'renewal_backend.settings.development')
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    os.environ.get('DJANGO_SETTINGS_MODULE', 'renewal_backend.settings.production')
)

app = Celery('renewal_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'fetch-incoming-emails': {
        'task': 'apps.email_manager.tasks.fetch_and_process_incoming_emails',
        'schedule': 300.0,  
    },
    'process-scheduled-emails': {
        'task': 'apps.email_manager.tasks.process_scheduled_emails',
        'schedule': 300.0,  
    },
    'process-renewal-reminders': {
        'task': 'apps.policies.tasks.process_renewal_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
}

app.conf.task_routes = {
    'apps.email_manager.tasks.*': {'queue': 'emails'},
    'apps.campaigns.tasks.*': {'queue': 'campaigns'},
    'apps.policies.tasks.*': {'queue': 'policies'},
    'apps.analytics.tasks.*': {'queue': 'analytics'},
}

@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
