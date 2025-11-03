import pandas as pd
import hashlib
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from apps.customers.models import Customer
from apps.files_upload.models import FileUpload
from apps.uploads.models import FileUpload as UploadsFileUpload
from apps.policies.models import Policy, PolicyType, PolicyAgent
from .utils import generate_customer_code, generate_case_number, generate_policy_number, generate_batch_code
from .serializers import (
    FileUploadSerializer,
    EnhancedFileUploadSerializer,
    FileUploadRequestSerializer
)

User = get_user_model()

def get_next_available_agent():
    try:
        available_agents = User.objects.filter(
            status='active',
            is_active=True
        ).annotate(
            current_workload=Count('assigned_customers')
        ).order_by('current_workload', 'first_name')

        if available_agents.exists():
            return available_agents.first()
        return None
    except Exception as e:
        print(f"Error getting next available agent: {e}")
        return None

def get_or_create_policy_agent(agent_name, agent_code=None):
    """Get or create a PolicyAgent based on agent_name and optional agent_code"""
    if not agent_name or not str(agent_name).strip():
        return None
    
    agent_name = str(agent_name).strip()
    
    try:
        # First try to find by agent_code if provided
        if agent_code and str(agent_code).strip():
            agent_code = str(agent_code).strip()
            agent = PolicyAgent.objects.filter(agent_code=agent_code).first()
            if agent:
                return agent
        
        # Try to find by agent_name
        agent = PolicyAgent.objects.filter(agent_name__iexact=agent_name).first()
        if agent:
            return agent
        
        # Create new agent
        agent = PolicyAgent.objects.create(
            agent_name=agent_name,
            agent_code=agent_code 
        )
        return agent
        
    except Exception as e:
        print(f"Error creating/finding policy agent: {e}")
        return None

def log_communication_attempt(customer, channel, outcome='successful', message_content='', response_received='', notes='', initiated_by=None):
    """Log a communication attempt with a customer"""
    from apps.customer_communication_preferences.models import CommunicationLog
    from django.utils import timezone
    
    try:
        CommunicationLog.objects.create(
            customer=customer,
            channel=channel,
            communication_date=timezone.now(),
            outcome=outcome,
            message_content=message_content,
            response_received=response_received,
            notes=notes,
            initiated_by=initiated_by
        )
        return True
    except Exception as e:
        print(f"Error logging communication attempt: {e}")
        return False

def get_customer_previous_policy_end_date(customer, current_policy_start_date=None, exclude_policy_id=None):
    from apps.policies.models import Policy

    try:
        # Handle both Customer instance and customer_id
        customer_id = customer.id if hasattr(customer, 'id') else customer

        # Build query to find previous policies
        query = Policy.objects.filter(customer_id=customer_id)

       
        if exclude_policy_id:
            query = query.exclude(id=exclude_policy_id)

       
        if current_policy_start_date:
            if isinstance(current_policy_start_date, datetime):
                current_policy_start_date = current_policy_start_date.date()
            query = query.filter(end_date__lt=current_policy_start_date)

       
        previous_policy = query.order_by('-end_date').first()

        if previous_policy:
            return previous_policy.end_date

        return None

    except Exception as e:
      
        print(f"Error getting previous policy end date: {e}")
        return None


def calculate_policy_and_renewal_status(end_date, start_date=None, grace_period_days=30,
                                      customer=None, exclude_policy_id=None):
    today = date.today()

    if isinstance(end_date, datetime):
        end_date = end_date.date()

    if isinstance(start_date, datetime):
        start_date = start_date.date()

    days_to_expiry = (end_date - today).days
    pre_due_threshold = 60
    policy_due_threshold = 15
    overdue_threshold = today - timedelta(days=grace_period_days)

    if start_date and start_date > end_date:
        return 'active', 'renewed'

    
    if customer and start_date:
        previous_policy_end_date = get_customer_previous_policy_end_date(
            customer, start_date, exclude_policy_id
        )

        if previous_policy_end_date and start_date > previous_policy_end_date:
           
            return 'active', 'renewed'

    
    if end_date < today:
        if end_date >= overdue_threshold:
            policy_status = 'expired'
            renewal_status = 'pending'
        else:
            policy_status = 'expired'
            renewal_status = 'overdue'

    elif 0 <= days_to_expiry <= policy_due_threshold:
        policy_status = 'pending'
        renewal_status = 'due'

    elif policy_due_threshold < days_to_expiry <= grace_period_days:
        policy_status = 'expiring_soon'
        renewal_status = 'due'

    elif grace_period_days < days_to_expiry <= pre_due_threshold:
        policy_status = 'active'
        renewal_status = 'not_required'

    else:
        policy_status = 'active'
        renewal_status = 'not_required'

    return policy_status, renewal_status

class FileUploadViewSet(viewsets.ModelViewSet):
    """Enhanced file upload viewset with comprehensive Excel processing"""

    queryset = FileUpload.objects.all()
    serializer_class = FileUploadSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """Upload and process Excel file with enhanced validation"""
        try:
            uploaded_file = request.FILES.get('file') or request.FILES.get('upload_file')
            if not uploaded_file:
                return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
            validation_result = self._validate_file(uploaded_file)
            if not validation_result['valid']:
                return Response({
                    'error': validation_result['error'],
                    'details': validation_result.get('details', {})
                }, status=status.HTTP_400_BAD_REQUEST)

            file_hash = self._calculate_file_hash(uploaded_file)
            existing_file = UploadsFileUpload.objects.filter(file_hash=file_hash).first()

            if existing_file:
                from django.utils import timezone
                from datetime import datetime
                
                # Format the uploaded date in a user-friendly way
                uploaded_date = existing_file.created_at
                if isinstance(uploaded_date, str):
                    uploaded_date = datetime.fromisoformat(uploaded_date.replace('Z', '+00:00'))
                
                formatted_date = uploaded_date.strftime('%B %d, %Y at %I:%M %p') if uploaded_date else 'Unknown'
                
                return Response({
                    'message': 'Duplicate file detected',
                    'details': {
                        'suggestion': 'This file already exists. Please upload a new file.'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                file_upload_record, uploads_record = self._create_file_records(
                    uploaded_file, file_hash, request.user
                )
            except Exception as create_error:
                raise create_error

            try:
                processing_result = self._process_uploaded_excel_file(uploads_record, request.user, file_upload_record)
                print(f"Processing result: {processing_result}")
                print(f"Uploads record status after processing: {uploads_record.status}")
                
              
                if not processing_result.get('valid', False):
                    # Delete file records when processing completely fails
                    try:
                        if file_upload_record:
                            file_upload_record.delete()
                        if uploads_record:
                            uploads_record.delete()
                    except Exception as delete_error:
                        print(f"Error deleting file records: {delete_error}")
                   
                    return Response({
                        'success': False,
                        'message': 'File processing failed',
                        'error': processing_result.get('error', 'Unknown processing error'),
                        'processing_details': processing_result
                    }, status=status.HTTP_400_BAD_REQUEST)
                
               
                if processing_result.get('failed_records', 0) > 0 and processing_result.get('successful_records', 0) == 0:
                    # All records failed - delete file records
                    try:
                        if file_upload_record:
                            file_upload_record.delete()
                        if uploads_record:
                            uploads_record.delete()
                    except Exception as delete_error:
                        print(f"Error deleting file records: {delete_error}")
                 
                    return Response({
                        'success': False,
                        'message': f'File processing failed. All {processing_result.get("total_records", 0)} records failed to process.',
                        'error': 'All records failed to process',
                        'processing_details': processing_result
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Partial success - some records succeeded, keep the file records
                if processing_result.get('failed_records', 0) > 0:
                    return Response({
                        'success': False,
                        'message': f'File processing completed with {processing_result.get("failed_records", 0)} failed records',
                        'error': f'{processing_result.get("failed_records", 0)} out of {processing_result.get("total_records", 0)} records failed to process',
                        'data': {
                            'uploads_file_id': uploads_record.pk,
                            'file_name': uploaded_file.name,
                            'file_size': uploaded_file.size,
                            'file_hash': file_hash,
                            'upload_status': 'partial',
                            'created_at': uploads_record.created_at.isoformat(),
                            'secure_filename': uploads_record.metadata.get('secure_filename', uploaded_file.name),
                            'category': uploads_record.category,
                            'subcategory': uploads_record.subcategory
                        },
                        'processing_details': processing_result
                    }, status=status.HTTP_207_MULTI_STATUS)
                
              
                if uploads_record.status == 'failed':
                    # Delete file records when status is failed
                    try:
                        if file_upload_record:
                            file_upload_record.delete()
                        if uploads_record:
                            uploads_record.delete()
                    except Exception as delete_error:
                        print(f"Error deleting file records: {delete_error}")
                    
                    return Response({
                        'success': False,
                        'message': 'File processing failed',
                        'error': uploads_record.error_message or 'Unknown processing error'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as process_error:
                print(f"Processing error: {str(process_error)}")
                print(f"Uploads record status: {uploads_record.status}")
                
                # Delete file records when processing throws an exception
                try:
                    if file_upload_record:
                        file_upload_record.delete()
                    if uploads_record:
                        uploads_record.delete()
                except Exception as delete_error:
                    print(f"Error deleting file records: {delete_error}")
              
                return Response({
                    'success': False,
                    'message': 'File processing failed due to an unexpected error',
                    'error': str(process_error)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            response_data = {
                'success': True,
                'message': 'File uploaded successfully',
                'data': {
                    'uploads_file_id': uploads_record.pk,
                    'file_name': uploaded_file.name,
                    'file_size': uploaded_file.size,
                    'file_hash': file_hash,
                    'upload_status': uploads_record.status,
                    'created_at': uploads_record.created_at.isoformat(),
                    'secure_filename': uploads_record.metadata.get('secure_filename', uploaded_file.name),
                    'category': uploads_record.category,
                    'subcategory': uploads_record.subcategory
                }
            }

            if file_upload_record and file_upload_record.processing_result:
                try:
                    import json
                    processing_details = json.loads(file_upload_record.processing_result) if isinstance(file_upload_record.processing_result, str) else file_upload_record.processing_result
                    response_data['processing_details'] = processing_details
                except (json.JSONDecodeError, TypeError):
                    response_data['processing_details'] = file_upload_record.processing_result

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            error_type = type(e).__name__
            print(f"Main exception caught: {error_type}: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

            return Response({
                'error': f'File processing failed: {str(e)}',
                'error_type': error_type,
                'details': {
                    'step': 'Exception caught in main try-catch',
                    'user': str(request.user),
                    'files_in_request': list(request.FILES.keys())
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _validate_file(self, file):
        """Enhanced file validation with security checks"""
        allowed_extensions = ['.xlsx', '.xls', '.csv', '.txt']
        allowed_mime_types = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
            'text/csv',
            'text/plain'
        ]

        file_extension = os.path.splitext(file.name)[1].lower()
        if file_extension not in allowed_extensions:
            return {
                'valid': False,
                'error': 'File format not supported. Please upload a CSV (.csv) or Excel (.xlsx, .xls) file.',
                'details': {
                    'supported_formats': ['CSV (.csv)', 'Excel (.xlsx)', 'Excel (.xls)'],
                    'file_extension': file_extension,
                    'allowed_extensions': allowed_extensions
                }
            }

        max_file_size = 50 * 1024 * 1024 
        if file.size > max_file_size:
            return {
                'valid': False,
                'error': 'File too large. Maximum size is 50MB.',
                'details': {
                    'file_size': file.size,
                    'max_size': max_file_size,
                    'file_size_mb': round(file.size / (1024 * 1024), 2)
                }
            }

        if hasattr(file, 'content_type') and file.content_type and file.content_type not in allowed_mime_types:
           
            if file.content_type.startswith('image/') or file.content_type.startswith('video/') or file.content_type.startswith('audio/'):
                return {
                    'valid': False,
                    'error': 'File format not supported. Please upload a CSV (.csv) or Excel (.xlsx, .xls) file.',
                    'details': {
                        'supported_formats': ['CSV (.csv)', 'Excel (.xlsx)', 'Excel (.xls)'],
                        'content_type': file.content_type
                    }
                }

        try:
            file.seek(0)
            header = file.read(8)
            file.seek(0)

           
            if file_extension in ['.xlsx', '.xls']:
                xlsx_signature = b'\x50\x4B\x03\x04' 
                xls_signature = b'\xD0\xCF\x11\xE0'  

                if not (header.startswith(xlsx_signature) or header.startswith(xls_signature)):
                    return {
                        'valid': False,
                        'error': 'Invalid Excel file format. Please upload a valid .xlsx or .xls file.',
                        'details': {
                            'supported_formats': ['CSV (.csv)', 'Excel (.xlsx)', 'Excel (.xls)'],
                            'file_extension': file_extension,
                            'file_signature': header.hex()
                        }
                    }
            
           

        except Exception:
            return {
                'valid': False,
                'error': 'Unable to validate file content.'
            }

        return {'valid': True}

    def _calculate_file_hash(self, file):
        """Calculate SHA-256 hash of the file"""
        hash_sha256 = hashlib.sha256()
        for chunk in file.chunks():
            hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _create_file_records(self, uploaded_file, file_hash, user):
        """Create records in both file upload tables with secure naming"""
        try:
            secure_filename = self._generate_secure_filename(uploaded_file.name, user.id)

            try:
                uploads_record = UploadsFileUpload.objects.create(
                    file=uploaded_file,
                    original_name=uploaded_file.name,
                    file_size=uploaded_file.size,
                    mime_type=uploaded_file.content_type,
                    file_hash=file_hash,
                    category='import',
                    subcategory='excel_data',
                    status='completed',
                    is_public=False,
                    created_by=user,
                    metadata={
                        'upload_source': 'policy_data_import',
                        'upload_timestamp': timezone.now().isoformat(),
                        'user_id': user.id,
                        'user_email': user.email,
                        'secure_filename': secure_filename,
                        'virus_scan_required': True
                    }
                )

                try:
                    file_upload_record = self._create_file_uploads_record(uploads_record, user)
                    print(f"Successfully created file_upload_record: {file_upload_record.id}")
                except Exception as e:
                    print(f"Failed to create file_upload_record: {str(e)}")
                    file_upload_record = None

            except Exception as e2:
                raise e2

            return file_upload_record, uploads_record

        except Exception as e:
            raise e

    def _generate_secure_filename(self, original_filename, user_id):
        """Generate secure filename with timestamp and user ID"""
        import uuid
        from datetime import datetime

        file_extension = os.path.splitext(original_filename)[1].lower()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        secure_filename = f"policy_import_{user_id}_{timestamp}_{unique_id}{file_extension}"

        return secure_filename

    def _create_file_uploads_record(self, uploads_record, user):
        """Create record in file_uploads table with all required fields"""
        import json
        try:
            file_upload_record = FileUpload.objects.create(
                uploaded_file=uploads_record.file,
                filename=uploads_record.original_name,
                original_filename=uploads_record.original_name,
                file_size=uploads_record.file_size,
                file_type=uploads_record.mime_type,
                upload_path=uploads_record.file.path if uploads_record.file else '',
                total_records=0,  
                successful_records=0,
                failed_records=0,
                upload_status='processing',
                uploaded_by=user,
                processing_started_at=timezone.now(),
                processing_result=json.dumps({
                    'file_info': {
                        'name': uploads_record.original_name,
                        'size': uploads_record.file_size,
                        'content_type': uploads_record.mime_type,
                        'hash': uploads_record.file_hash,
                    },
                    'processing_status': 'started',
                    'timestamp': timezone.now().isoformat(),
                    'columns_processed': [],
                    'validation_errors': [],
                    'processing_errors': []
                }),
                created_by=user,
            )
            return file_upload_record
        except Exception as e:
            raise e

    def _read_file_data(self, file_path, file_name):
        """Read file data based on file extension (Excel or CSV)"""
        file_extension = os.path.splitext(file_name)[1].lower()
        
        if file_extension == '.csv':
            
            try:
              
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                   
                    df = pd.read_csv(file_path, encoding='latin-1')
                except UnicodeDecodeError:
                    try:
                       
                        df = pd.read_csv(file_path, encoding='cp1252')
                    except UnicodeDecodeError:
                        try:
                           
                            df = pd.read_csv(file_path, encoding='utf-8-sig')
                        except UnicodeDecodeError:
                            df = pd.read_csv(file_path, encoding='utf-8', errors='replace')
        elif file_extension in ['.xlsx', '.xls']:
          
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        df = df.dropna(how='all')  
        df = df[~(df.astype(str).eq('').all(axis=1))]
        
        # Remove 'id' column if it exists to prevent primary key conflicts
        # Users should not provide ID as it's auto-generated
        if 'id' in df.columns:
            df = df.drop(columns=['id'])
        
        return df

    def _process_uploaded_excel_file(self, uploads_record, user, file_upload_record=None):
        """Process Excel/CSV file directly from uploads_record"""
        try:
            df = self._read_file_data(uploads_record.file.path, uploads_record.original_name)

            validation_result = self._validate_excel_structure_flexible(df)
            if not validation_result['valid']:
                uploads_record.status = 'failed'
                uploads_record.error_message = validation_result['error']
                uploads_record.save()
              
                return {
                    'valid': False,
                    'error': validation_result['error'],
                    'total_records': 0,
                    'successful_records': 0,
                    'failed_records': 0,
                    'created_customers': 0,
                    'created_policies': 0,
                    'created_renewal_cases': 0,
                    'errors': [validation_result['error']]
                }

            processing_result = self._process_excel_data(df, user)

            uploads_record.status = 'completed' if processing_result['failed_records'] == 0 else 'partial'
            uploads_record.metadata.update({
                'processing_completed': True,
                'total_records': processing_result['total_records'],
                'successful_records': processing_result['successful_records'],
                'failed_records': processing_result['failed_records'],
                'created_customers': processing_result['created_customers'],
                'created_policies': processing_result['created_policies'],
                'created_renewal_cases': processing_result['created_renewal_cases']
            })
            uploads_record.save()

            if file_upload_record:
                file_upload_record.upload_status = 'completed' if processing_result['failed_records'] == 0 else 'partial'
                file_upload_record.total_records = processing_result['total_records']
                file_upload_record.successful_records = processing_result['successful_records']
                file_upload_record.failed_records = processing_result['failed_records']
                file_upload_record.processing_completed_at = timezone.now()
                import json
                processing_summary = {
                    'status': 'completed' if processing_result['failed_records'] == 0 else 'partial',
                    'total_records': processing_result['total_records'],
                    'successful_records': processing_result['successful_records'],
                    'failed_records': processing_result['failed_records'],
                    'created_customers': processing_result['created_customers'],
                    'created_policies': processing_result['created_policies'],
                    'created_renewal_cases': processing_result['created_renewal_cases'],
                    'errors': processing_result.get('errors', [])
                }
                file_upload_record.processing_result = json.dumps(processing_summary)

                file_upload_record.save()
                print(f"Updated file_upload_record status to: {file_upload_record.upload_status}")
            else:
                print("Warning: file_upload_record is None, trying to find and update by uploads_record")
               
                try:
                    file_upload_record = FileUpload.objects.filter(
                        original_filename=uploads_record.original_name,
                        file_size=uploads_record.file_size
                    ).order_by('-created_at').first()
                    
                    if file_upload_record:
                        file_upload_record.upload_status = 'completed' if processing_result['failed_records'] == 0 else 'partial'
                        file_upload_record.total_records = processing_result['total_records']
                        file_upload_record.successful_records = processing_result['successful_records']
                        file_upload_record.failed_records = processing_result['failed_records']
                        file_upload_record.processing_completed_at = timezone.now()
                        import json
                        processing_summary = {
                            'status': 'completed' if processing_result['failed_records'] == 0 else 'partial',
                            'total_records': processing_result['total_records'],
                            'successful_records': processing_result['successful_records'],
                            'failed_records': processing_result['failed_records'],
                            'created_customers': processing_result['created_customers'],
                            'created_policies': processing_result['created_policies'],
                            'created_renewal_cases': processing_result['created_renewal_cases'],
                            'errors': processing_result.get('errors', [])
                        }
                        file_upload_record.processing_result = json.dumps(processing_summary)
                        file_upload_record.save()
                        print(f"Found and updated file_upload_record status to: {file_upload_record.upload_status}")
                    else:
                        print("Could not find file_upload_record to update")
                except Exception as e:
                    print(f"Error trying to find and update file_upload_record: {str(e)}")


       
            processing_result['valid'] = True
            return processing_result

        except Exception as e:
         
            print(f"Error in _process_uploaded_excel_file: {str(e)}")
            
            uploads_record.status = 'failed'
            uploads_record.error_message = str(e)
            uploads_record.updated_by = user
            uploads_record.save()
            
          
            return {
                'valid': False,
                'error': str(e),
                'total_records': 0,
                'successful_records': 0,
                'failed_records': 0,
                'created_customers': 0,
                'created_policies': 0,
                'created_renewal_cases': 0,
                'errors': [str(e)]
            }

    def _validate_excel_structure_flexible(self, df):
        core_required = ['first_name', 'last_name', 'email']

        missing_core = [col for col in core_required if col not in df.columns]

        if missing_core:
            return {
                'valid': False,
                'error': f"Missing core required columns: {', '.join(missing_core)}"
            }

        if df.empty:
            return {
                'valid': False,
                'error': "File is empty"
            }

        available_columns = list(df.columns)
        print(f"Available columns in file: {available_columns}")

        has_channel = 'channel' in df.columns
        has_channel_source = 'channel_source' in df.columns

        if has_channel or has_channel_source:
            print(f"Channel tracking columns found - channel: {has_channel}, channel_source: {has_channel_source}")

        return {'valid': True}

    def _process_excel_file(self, file_upload_record, uploads_record, user):
        """Process Excel/CSV file and extract data"""
        try:
            df = self._read_file_data(file_upload_record.uploaded_file.path, file_upload_record.original_filename)

            validation_result = self._validate_excel_structure(df)
            if not validation_result['valid']:
                self._mark_processing_failed(
                    file_upload_record, uploads_record, validation_result['error'], user
                )
                return validation_result

            processing_result = self._process_excel_data(df, user)

            self._update_file_records_with_results(
                file_upload_record, uploads_record, processing_result, user
            )

            return processing_result

        except Exception as e:
            error_msg = f"File processing error: {str(e)}"
            self._mark_processing_failed(file_upload_record, uploads_record, error_msg, user)
            return {'error': error_msg, 'valid': False}

    def _validate_excel_structure(self, df):
        required_columns = [
            'first_name', 'last_name', 'email', 'phone', 'date_of_birth',
            'gender', 'address_line1', 'kyc_status', 'kyc_documents',
            'communication_preferences', 'policy_number', 'policy_type',
            'premium_amount', 'start_date', 'end_date', 'nominee_name',
            'nominee_relationship', 'agent_name', 'agent_code',
            'renewal_amount',
            'notes'
        ]


        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return {
                'valid': False,
                'error': f"Missing required columns: {', '.join(missing_columns)}"
            }

        if df.empty:
            return {
                'valid': False,
                'error': "Excel file is empty"
            }

        return {'valid': True}

    def _process_excel_data(self, df, user):
        """Process Excel data and create database records"""
        total_records = len(df)
        successful_records = 0
        failed_records = 0
        errors = []
        created_customers = 0
        created_policies = 0
        created_renewal_cases = 0

        batch_code = generate_batch_code()

        for idx, (_, row) in enumerate(df.iterrows()):
            try:
                with transaction.atomic():
                    customer, customer_created = self._process_customer_data(row, user)
                    if customer_created:
                        created_customers += 1

                    policy, policy_created = self._process_policy_data(row, customer, user)
                    if policy_created:
                        created_policies += 1

                    self._process_renewal_case_data(row, customer, policy, user, batch_code)
                    created_renewal_cases += 1

                    successful_records += 1

            except Exception as e:
                failed_records += 1
                error_msg = f"Row {idx + 1}: {str(e)}"
                errors.append(error_msg)

        return {
            'total_records': total_records,
            'successful_records': successful_records,
            'failed_records': failed_records,
            'errors': errors,
            'created_customers': created_customers,
            'created_policies': created_policies,
            'created_renewal_cases': created_renewal_cases,
            'valid': True
        }

    def _process_customer_data(self, row, user):
        """Process customer data from Excel row"""
        email = str(row.get('email', '')).strip().lower() if row.get('email') and pd.notna(row.get('email')) else ''
        if not email:
            raise ValueError("Email is required for customer creation")
        
        first_name = str(row.get('first_name', '')).strip() if row.get('first_name') and pd.notna(row.get('first_name')) else ''
        if not first_name:
            raise ValueError("First name is required for customer creation")
        
        phone = str(row.get('phone', '')).strip() if row.get('phone') and pd.notna(row.get('phone')) else ''

        customer = Customer.objects.filter(email__iexact=email).first()

        if not customer and phone:
            customer = Customer.objects.filter(phone=phone).first()

        customer_created = False

        if not customer:
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    customer_code = generate_customer_code()

                    assigned_agent = get_next_available_agent()
                    
                    try:
                        channel_obj = self._get_or_create_channel(row, user)
                    except Exception as channel_error:
                        print(f"Error getting/creating channel: {channel_error}")
                        channel_obj = None  

                    with transaction.atomic():
                        if attempt == 0: 
                            from django.db import connection
                            with connection.cursor() as cursor:
                                cursor.execute("""
                                    SELECT setval(
                                        pg_get_serial_sequence('customers', 'id'),
                                        COALESCE((SELECT MAX(id) FROM customers), 0) + 1,
                                        false
                                    )
                                """)
                        
                        customer = Customer.objects.create(
                            customer_code=customer_code,
                            first_name=first_name,
                            last_name=str(row.get('last_name', '')).strip() if row.get('last_name') and pd.notna(row.get('last_name')) else '',
                            email=email,
                            phone=phone,
                            date_of_birth=self._parse_date(row.get('date_of_birth')),
                            gender=str(row.get('gender', 'male')).lower() if row.get('gender') and pd.notna(row.get('gender')) else 'male',
                            address_line1=str(row.get('address_line1', '') or row.get('address', '')),
                            address_line2=str(row.get('address_line2', '')),
                            city=str(row.get('city', '')),
                            state=str(row.get('state', '')),
                            postal_code=str(row.get('postalcode', '') or row.get('postal_code', '')),
                            country=str(row.get('country', 'India')),
                            kyc_status=str(row.get('kyc_status', 'pending')).lower() if row.get('kyc_status') and pd.notna(row.get('kyc_status')) else 'pending',
                            kyc_documents=str(row.get('kyc_documents', '')),
                            assigned_agent=assigned_agent,
                            channel_id=channel_obj,
                            created_by=user,
                            updated_by=None
                        )
                    # Verify customer was actually created before setting flag
                    if customer and customer.id:
                        customer_created = True

                    if assigned_agent:
                        print(f" Auto-assigned agent {assigned_agent.get_full_name()} to customer {customer.customer_code}")
                    else:
                        print(f"  No agents available for auto-assignment to customer {customer.customer_code}")

                    break
                except IntegrityError as e:
                    error_message = str(e).lower()
                    if 'customer_code' in error_message and attempt < max_retries - 1:
                        continue
                    elif 'customer_pkey' in error_message or 'duplicate key' in error_message:
                        if attempt < max_retries - 1:
                            from django.db import connection
                            try:
                                with connection.cursor() as cursor:
                                    cursor.execute("""
                                        SELECT setval(
                                            pg_get_serial_sequence('customers', 'id'),
                                            COALESCE((SELECT MAX(id) FROM customers), 0) + 1,
                                            false
                                        )
                                    """)
                                print(f"Fixed customer ID sequence on attempt {attempt + 1}")
                                continue
                            except Exception as seq_error:
                                print(f"Error fixing sequence: {seq_error}")
                                raise e
                    else:
                        raise
        else:
            channel_obj = self._get_or_create_channel(row, user)
            if channel_obj and not customer.channel_id:
                customer.channel_id = channel_obj
                customer.updated_by = user
                customer.save(update_fields=['channel_id', 'updated_by', 'updated_at'])

        try:
            comm_pref_raw = str(row.get('communication_preferences', '') or '').strip()
            if comm_pref_raw and customer:
                with transaction.atomic():
                    tokens = [t.strip().lower() for t in comm_pref_raw.replace(';', ',').split(',') if t and t.strip()]
                    email_enabled = 'email' in tokens
                    sms_enabled = 'sms' in tokens
                    phone_enabled = ('phone' in tokens) or ('call' in tokens)
                    whatsapp_enabled = 'whatsapp' in tokens
                    postal_mail_enabled = ('postal' in tokens) or ('postal_mail' in tokens) or ('mail' in tokens)
                    push_notification_enabled = ('push' in tokens) or ('in_app' in tokens) or ('notification' in tokens)

                 
                    valid_channels = ['email', 'sms', 'phone', 'whatsapp', 'postal_mail', 'push_notification']
                    preferred_channel = next((t for t in tokens if t in valid_channels), 'email')
                    if preferred_channel == 'mail':
                        preferred_channel = 'postal_mail'
                    if preferred_channel == 'push':
                        preferred_channel = 'push_notification'

                    from apps.customer_communication_preferences.models import CustomerCommunicationPreference

                    comm_obj, created = CustomerCommunicationPreference.objects.get_or_create(
                        customer=customer,
                        communication_type='policy_renewal',  
                        defaults={
                            'preferred_channel': preferred_channel,
                            'email_enabled': email_enabled,
                            'sms_enabled': sms_enabled,
                            'phone_enabled': phone_enabled,
                            'whatsapp_enabled': whatsapp_enabled,
                            'postal_mail_enabled': postal_mail_enabled,
                            'push_notification_enabled': push_notification_enabled,
                            'preferred_language': getattr(customer, 'preferred_language', 'en') or 'en',
                            'created_by': user,
                            'updated_by': None,
                        }
                    )

                    if not created:
                        comm_obj.preferred_channel = preferred_channel or comm_obj.preferred_channel
                        comm_obj.email_enabled = email_enabled or comm_obj.email_enabled
                        comm_obj.sms_enabled = sms_enabled or comm_obj.sms_enabled
                        comm_obj.phone_enabled = phone_enabled or comm_obj.phone_enabled
                        comm_obj.whatsapp_enabled = whatsapp_enabled or comm_obj.whatsapp_enabled
                        comm_obj.postal_mail_enabled = postal_mail_enabled or comm_obj.postal_mail_enabled
                        comm_obj.push_notification_enabled = push_notification_enabled or comm_obj.push_notification_enabled
                        comm_obj.updated_by = user
                        comm_obj.save(update_fields=[
                            'preferred_channel','email_enabled','sms_enabled','phone_enabled',
                            'whatsapp_enabled','postal_mail_enabled','push_notification_enabled','updated_by'
                        ])
        except Exception as comm_error:
            print(f"Error processing communication preferences: {comm_error}")
            pass

        if not customer:
            raise ValueError(f"Failed to create or find customer for email: {email}")
        
        return customer, customer_created

    def _process_policy_data(self, row, customer, user):
        excel_policy_number = row.get('policy_number')
        if excel_policy_number and str(excel_policy_number).strip():
            policy_number = str(excel_policy_number).strip()
        else:
            policy_number = generate_policy_number()

        policy = Policy.objects.filter(policy_number=policy_number).first()
        policy_created = False

        if not policy:
            policy_type_name = str(row.get('policy_type', 'General'))
            policy_type, _ = PolicyType.objects.get_or_create(
                name=policy_type_name,
                defaults={
                    'code': policy_type_name.upper()[:10],
                    'description': f'Auto-created policy type for {policy_type_name}',
                    'created_by': user,
                    'updated_by': user
                }
            )

            payment_frequency = str(row.get('payment_frequency', 'yearly')).lower() if row.get('payment_frequency') and pd.notna(row.get('payment_frequency')) else 'yearly'
            if payment_frequency not in ['monthly', 'quarterly', 'half_yearly', 'yearly']:
                payment_frequency = 'yearly'

            start_date = self._parse_date(row.get('start_date'))
            end_date = self._parse_date(row.get('end_date'))

            if start_date is None:
                from datetime import date
                start_date = date.today()

            if end_date is None:
                from datetime import date, timedelta
                if payment_frequency == 'monthly':
                    end_date = start_date + timedelta(days=30)
                elif payment_frequency == 'quarterly':
                    end_date = start_date + timedelta(days=90)
                elif payment_frequency == 'half_yearly':
                    end_date = start_date + timedelta(days=180)
                else:  
                    end_date = start_date + timedelta(days=365)

            policy_status, _ = calculate_policy_and_renewal_status(
                end_date,
                start_date=start_date,
                customer=customer
            )

            agent_name = str(row.get('agent_name', '')).strip()
            agent_code = str(row.get('agent_code', '')).strip() if row.get('agent_code') else None
            policy_agent = get_or_create_policy_agent(agent_name, agent_code)

            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT setval(
                            pg_get_serial_sequence('policies', 'id'),
                            COALESCE((SELECT MAX(id) FROM policies), 0) + 1,
                            false
                        )
                    """)
            except Exception as seq_error:
                print(f"Warning: Could not fix policy sequence: {seq_error}")

            policy = Policy.objects.create(
                policy_number=policy_number,
                customer=customer,
                policy_type=policy_type,
                start_date=start_date,
                end_date=end_date,
                premium_amount=Decimal(str(row.get('premium_amount', 0))),
                sum_assured=Decimal(str(row.get('sum_assured', 0))),
                payment_frequency=payment_frequency,
                status=policy_status,
                nominee_name=str(row.get('nominee_name', '')),
                nominee_relationship=str(row.get('nominee_relationship', '')),
                nominee_contact=str(row.get('nominee_contact', '')),
                agent=policy_agent, 
                created_by=user,
                last_modified_by=user
            )
            policy_created = True

        return policy, policy_created

    def _process_renewal_case_data(self, row, customer, policy, user, batch_code):
        max_retries = 5
        case_number = None
        for attempt in range(max_retries):
            case_number = generate_case_number()
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM renewal_cases WHERE case_number = %s", [case_number])
                result = cursor.fetchone()
                if result and result[0] == 0:
                    break
            if attempt == max_retries - 1:
                raise ValueError(f"Could not generate unique case number after {max_retries} attempts")

        policy_status, calculated_renewal_status = calculate_policy_and_renewal_status(
            policy.end_date,
            start_date=policy.start_date,
            customer=customer
        )
        
        
        if calculated_renewal_status == 'not_required':
            renewal_status = 'pending'
        else:
            renewal_status = calculated_renewal_status

        renewal_amount = row.get('renewal_amount')
        if renewal_amount is None or pd.isna(renewal_amount):
            renewal_amount = policy.premium_amount
        else:
            renewal_amount = Decimal(str(renewal_amount))

        assigned_to_id = None
        if 'assigned_to' in row and row['assigned_to']:
            assigned_to_value = str(row['assigned_to']).strip()
            from django.contrib.auth import get_user_model
            from django.db import models
            User = get_user_model()

            if assigned_to_value.isdigit():
                try:
                    assigned_user = User.objects.get(id=int(assigned_to_value))
                    assigned_to_id = assigned_user.pk
                except User.DoesNotExist:
                    assigned_user = None

            if not assigned_to_id:
                assigned_user = User.objects.filter(
                    models.Q(email=assigned_to_value) | models.Q(employee_id=assigned_to_value)
                ).first()
                if assigned_user:
                    assigned_to_id = assigned_user.pk

        if not assigned_to_id:
            assigned_to_id = user.id

        from apps.renewals.models import RenewalCase
        from django.contrib.auth import get_user_model
        User = get_user_model()

        assigned_user = None
        if assigned_to_id:
            try:
                assigned_user = User.objects.get(id=assigned_to_id)
            except User.DoesNotExist:
                assigned_user = user  
        else:
            assigned_user = user

        customer_payment_obj = None
        try:
            from uuid import uuid4
            from apps.customer_payments.models import CustomerPayment

            payment_date_raw = row.get('payment_date') or row.get('last_contact_date')
            payment_date_parsed = self._parse_datetime(payment_date_raw)
            if payment_date_parsed:
                with transaction.atomic():
                    payment_mode_value = str(row.get('payment_mode', 'cash')).lower() if row.get('payment_mode') and pd.notna(row.get('payment_mode')) else 'cash'
                    payment_amount_value = renewal_amount 
                    transaction_id_value = f"IMP-{batch_code}-{case_number}-{uuid4().hex[:8]}"

                  
                    customer_payment_obj = CustomerPayment.objects.create(
                        payment_amount=payment_amount_value,
                        payment_status='pending',  
                        payment_date=payment_date_parsed,
                        payment_mode=payment_mode_value,
                        transaction_id=transaction_id_value,
                        net_amount=payment_amount_value,
                        created_by=user,
                        updated_by=user
                    )
        except Exception:
            customer_payment_obj = None

        renewal_case = RenewalCase.objects.create(
            case_number=case_number,
            batch_code=batch_code,
            customer=customer,
            policy=policy,
            status=renewal_status,
           
            renewal_amount=renewal_amount,
            notes=str(row.get('notes', '')),
            assigned_to=assigned_user,
            created_by=user,
            updated_by=None,
            customer_payment=customer_payment_obj
        )
        
        if customer.channel_id:
            channel_name = str(customer.channel_id.name).lower() if customer.channel_id.name and pd.notna(customer.channel_id.name) else 'email'
            channel_mapping = {
                'email': 'email',
                'sms': 'sms',
                'whatsapp': 'whatsapp',
                'phone': 'phone',
                'call': 'phone',
                'push': 'push_notification',
                'in_app': 'in_app'
            }
            comm_channel = channel_mapping.get(channel_name, 'email')
            log_communication_attempt(
                customer=customer,
                channel=comm_channel,
                outcome='successful',
                message_content=f'Renewal case created: {case_number}',
                notes=f'Initial renewal case creation via {channel_name}',
                initiated_by=user
            )

        return renewal_case

    def _get_or_create_channel(self, row, user):
        """Get or create channel based on Excel data"""
        from apps.channels.models import Channel

        channel_name = str(row.get('channel', 'Online')).strip()
        channel_source = str(row.get('channel_source', 'Website')).strip()

        channel_name_normalized = str(channel_name).lower() if channel_name and pd.notna(channel_name) else 'email'
        channel_source_normalized = str(channel_source).lower() if channel_source and pd.notna(channel_source) else 'website'

        combined_name = f"{channel_name} - {channel_source}"

        channel_type_mapping = {
            'online': 'Online',
            'mobile': 'Mobile',
            'offline': 'Offline',
            'phone': 'Phone',
            'agent': 'Agent',
            'telecalling': 'Phone',
            'call center': 'Phone',
            'partner': 'Agent',
            'branch': 'Offline',
            'website': 'Online',
            'mobile app': 'Mobile'
        }

        channel_type = 'Online'
        for key, value in channel_type_mapping.items():
            if key in channel_name_normalized:
                channel_type = value
                break

        existing_channel = Channel.objects.filter(
            name__iexact=combined_name
        ).first()

        if existing_channel:
            return existing_channel

        try:
            with transaction.atomic():
                new_channel = Channel.objects.create(
                    name=combined_name,
                    channel_type=channel_type,
                    description=f"Auto-created from Excel upload - Channel: {channel_name}, Source: {channel_source}",
                    status='active',
                    priority='medium',
                    created_by=user
                )
            return new_channel
        except Exception as e:
            default_channel = Channel.objects.filter(name__iexact='Online - Website').first()
            if default_channel:
                return default_channel

            default_channel = Channel.objects.create(
                name='Online - Website',
                channel_type='Online',
                description='Default channel for online website traffic',
                status='active',
                priority='medium',
                created_by=user
            )
            return default_channel

    def _parse_date(self, date_value):
        """Parse date from various formats"""
        if pd.isna(date_value) or date_value is None:
            return None

        if isinstance(date_value, (date, datetime)):
            return date_value.date() if isinstance(date_value, datetime) else date_value

        try:
            return pd.to_datetime(date_value).date()
        except:
            return None

    def _parse_datetime(self, datetime_value):
        """Parse datetime from various formats"""
        if pd.isna(datetime_value) or datetime_value is None:
            return None

        if isinstance(datetime_value, datetime):
            return datetime_value

        if isinstance(datetime_value, date):
            return datetime.combine(datetime_value, datetime.min.time())

        try:
            return pd.to_datetime(datetime_value)
        except:
            return None

    def _update_file_records_with_results(self, file_upload_record, uploads_record, result, user):
        file_upload_record.total_records = result['total_records']
        file_upload_record.successful_records = result['successful_records']
        file_upload_record.failed_records = result['failed_records']
        file_upload_record.upload_status = 'completed' if result['failed_records'] == 0 else 'partial'
        file_upload_record.processing_completed_at = timezone.now()


        import json

        result_summary = {
            'processing_summary': f"Processing completed. Total: {result['total_records']}, Success: {result['successful_records']}, Failed: {result['failed_records']}",
            'total_records': result['total_records'],
            'successful_records': result['successful_records'],
            'failed_records': result['failed_records'],
            'errors': result.get('errors', [])[:3],  
            'status': 'completed' if result['failed_records'] == 0 else 'partial',
            'created_customers': result.get('created_customers', 0),
            'created_policies': result.get('created_policies', 0),
            'created_renewal_cases': result.get('created_renewal_cases', 0)
        }

        file_upload_record.error_details = result_summary
        file_upload_record.processing_result = json.dumps(result_summary) 
        file_upload_record.save()

        uploads_record.status = 'completed' if result['failed_records'] == 0 else 'failed'
        uploads_record.error_message = result_summary['processing_summary']
        uploads_record.processing_result = json.dumps(result_summary) 

        uploads_record.save(update_fields=['status', 'error_message', 'processing_result'])

    def _mark_processing_failed(self, file_upload_record, uploads_record, error_msg, user):
       
        import json

        failure_result = {
            'status': 'failed',
            'error': error_msg,
            'type': 'processing_failed',
            'total_records': 0,
            'successful_records': 0,
            'failed_records': 0,
            'created_customers': 0,
            'created_policies': 0,
            'created_renewal_cases': 0
        }

        file_upload_record.upload_status = 'failed'
        file_upload_record.error_details = failure_result
        file_upload_record.processing_result = json.dumps(failure_result)
        file_upload_record.processing_completed_at = timezone.now()

        file_upload_record.save()

        uploads_record.status = 'failed'
        uploads_record.error_message = error_msg
        uploads_record.processing_result = json.dumps(failure_result)

        uploads_record.save(update_fields=['status', 'error_message', 'processing_result'])

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
       
        try:
            file_upload = FileUpload.objects.get(pk=pk)

            return Response({
                'id': file_upload.pk,
                'filename': file_upload.original_filename,
                'status': file_upload.upload_status,
                'total_records': file_upload.total_records,
                'successful_records': file_upload.successful_records,
                'failed_records': file_upload.failed_records,
                'processing_summary': file_upload.error_details.get('processing_summary', '') if file_upload.error_details else '',
                'created_at': file_upload.created_at,
                'processing_started_at': file_upload.processing_started_at,
                'processing_completed_at': file_upload.processing_completed_at
            })
        except FileUpload.DoesNotExist:
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)


