# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
# from .celery import app as celery_app  # Commented out until Celery is installed

# __all__ = ('celery_app',) 