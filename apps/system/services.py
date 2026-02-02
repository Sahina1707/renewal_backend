import os
import shutil
import logging
import boto3
from datetime import datetime
from django.conf import settings
from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

class BackupService:
    """Service to handle database backups and upload to S3."""
    
    @staticmethod
    def create_backup():
        """
        Creates a database backup and uploads it to S3.
        Returns the S3 URL of the backup or None if failed.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"db_backup_{timestamp}.sql"
        backup_path = os.path.join(settings.BASE_DIR, 'backups')
        
        # Ensure backups directory exists
        if not os.path.exists(backup_path):
            os.makedirs(backup_path)
            
        local_file_path = os.path.join(backup_path, backup_filename)
        
        try:
            logger.info(f"Starting database backup: {backup_filename}")
            
            # Determine database engine
            db_engine = settings.DATABASES['default']['ENGINE']
            
            if 'postgresql' in db_engine:
                BackupService._backup_postgresql(local_file_path)
            elif 'sqlite' in db_engine:
                # For SQLite, we just copy the file
                # Change extension to .sqlite3
                local_file_path = local_file_path.replace('.sql', '.sqlite3') 
                backup_filename = os.path.basename(local_file_path)
                BackupService._backup_sqlite(local_file_path)
            else:
                logger.error(f"Unsupported database engine for backup: {db_engine}")
                return None
                
            # Upload to S3
            s3_url = BackupService._upload_to_s3(local_file_path, backup_filename)
            
            # Clean up local file
            if os.path.exists(local_file_path):
                os.remove(local_file_path)
                
            return s3_url
            
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            # Try to clean up if file exists
            if os.path.exists(local_file_path):
                try:
                    os.remove(local_file_path)
                except:
                    pass
            return None

    @staticmethod
    def _backup_postgresql(output_path):
        """Creates a PostgreSQL dump."""
        db_settings = settings.DATABASES['default']
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']
        db_password = db_settings['PASSWORD']
        
        # Set PGPASSWORD environment variable so pg_dump doesn't ask for password
        env = os.environ.copy()
        env['PGPASSWORD'] = str(db_password)
        
        # Construct pg_dump command
        # Note: pg_dump must be in system PATH
        command = f"pg_dump -h {db_host} -p {db_port} -U {db_user} -F c -b -v -f \"{output_path}\" {db_name}"
        
        logger.info(f"Running pg_dump for {db_name}...")
        exit_code = os.system(f"{command}")
        
        if exit_code != 0:
            raise Exception(f"pg_dump failed with exit code {exit_code}")

    @staticmethod
    def _backup_sqlite(output_path):
        """Creates a SQLite backup."""
        db_name = settings.DATABASES['default']['NAME']
        if not os.path.exists(db_name):
             raise Exception(f"Database file not found: {db_name}")
             
        shutil.copy2(db_name, output_path)

    @staticmethod
    def _upload_to_s3(file_path, filename):
        """Uploads the file to S3."""
        if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME]):
            logger.warning("AWS credentials not configured. Skipping S3 upload.")
            return None

        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        s3_key = f"backups/{filename}"
        
        logger.info(f"Uploading {filename} to S3 bucket {settings.AWS_STORAGE_BUCKET_NAME}...")
        s3_client.upload_file(file_path, settings.AWS_STORAGE_BUCKET_NAME, s3_key)
        
        url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        logger.info(f"Backup uploaded successfully: {url}")
        return url
