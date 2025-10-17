import logging
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg, Max, Min
from django.contrib.auth import get_user_model

# OpenAI imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

from apps.renewals.models import RenewalCase
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.customer_communication_preferences.models import CommunicationLog
from apps.customer_payments.models import CustomerPayment

User = get_user_model()
logger = logging.getLogger(__name__)


class CaseTrackingChatbotService:
    """Service for handling case tracking and customer-related chatbot queries"""
    
    def __init__(self):
        self.openai_client = None
        self._initialize_openai()
    
    def _initialize_openai(self):
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not available")
            return False
        
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            logger.warning("OpenAI API key not configured")
            return False
        
        try:
            self.openai_client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """Check if the service is available"""
        return self.openai_client is not None
    
    def get_case_tracking_data(self) -> Dict[str, Any]:
        """Get comprehensive data for case tracking analysis"""
        try:
            # Get case statistics
            cases = RenewalCase.objects.filter(is_deleted=False)
            
            case_stats = {
                'total_cases': cases.count(),
                'pending_cases': cases.filter(status='pending').count(),
                'in_progress_cases': cases.filter(status='in_progress').count(),
                'completed_cases': cases.filter(status='completed').count(),
                'renewed_cases': cases.filter(status='renewed').count(),
                'cancelled_cases': cases.filter(status='cancelled').count(),
                'expired_cases': cases.filter(status='expired').count(),
                'due_cases': cases.filter(status='due').count(),
                'overdue_cases': cases.filter(status='overdue').count(),
                'assigned_cases': cases.filter(status='assigned').count(),
                'not_required_cases': cases.filter(status='not_required').count(),
                'failed_cases': cases.filter(status='failed').count(),
                'uploaded_cases': cases.filter(status='uploaded').count(),
            }
            
            # Get customer statistics
            customers = Customer.objects.filter(is_deleted=False)
            customer_stats = {
                'total_customers': customers.count(),
                'active_customers': customers.filter(status='active').count(),
                'inactive_customers': customers.filter(status='inactive').count(),
                'prospect_customers': customers.filter(status='prospect').count(),
                'normal_profile_customers': customers.filter(profile='Normal').count(),
                'hni_profile_customers': customers.filter(profile='HNI').count(),
            }
            
            # Get case performance by status
            case_performance = cases.values('status').annotate(
                count=Count('id'),
                avg_amount=Avg('renewal_amount'),
                total_amount=Sum('renewal_amount')
            )
            
            # Get customer profile distribution
            customer_profiles = customers.values('profile').annotate(
                count=Count('id')
            )
            
            # Get recent cases
            recent_cases = cases.order_by('-created_at')[:10].values(
                'case_number', 'status', 'renewal_amount', 'customer__first_name', 
                'customer__last_name', 'customer__profile', 'customer__phone',
                'policy__policy_number', 'policy__policy_type__name', 'created_at'
            )
            
            # Get payment statistics
            payment_stats = cases.aggregate(
                total_pending_amount=Sum('renewal_amount', filter=Q(payment_status='pending')),
                total_success_amount=Sum('renewal_amount', filter=Q(payment_status='success')),
                total_failed_amount=Sum('renewal_amount', filter=Q(payment_status='failed')),
                avg_renewal_amount=Avg('renewal_amount')
            )
            
            # Get communication statistics
            communication_stats = CommunicationLog.objects.aggregate(
                total_communications=Count('id'),
                successful_communications=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])),
                failed_communications=Count('id', filter=Q(outcome__in=['failed', 'bounced', 'blocked']))
            )
            
            return {
                'case_stats': case_stats,
                'customer_stats': customer_stats,
                'case_performance': list(case_performance),
                'customer_profiles': list(customer_profiles),
                'recent_cases': list(recent_cases),
                'payment_stats': payment_stats,
                'communication_stats': communication_stats,
                'timestamp': timezone.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error fetching case tracking data: {str(e)}")
            return {}
    
    def generate_ai_response(self, user_message: str, context_data: Dict[str, Any] = None, user=None, conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not available',
                'message': 'OpenAI API key not configured or service unavailable'
            }
        
        try:
            # Classify the query type to determine what data to fetch
            query_type = self._classify_query(user_message)
            
            
            if query_type == 'non_case_tracking':
                return {
                    'success': True,
                    'response': 'Sorry, I can only help with case tracking and customer-related questions.',
                    'model': 'direct-response',
                    'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
                    'timestamp': timezone.now().isoformat()
                }
            
            # Fetch relevant data based on query type
            dashboard_data = self.get_case_tracking_data()
            specialized_data = self._get_specialized_data(query_type, user_message)
            dashboard_data.update(specialized_data)
            
            system_prompt = self._create_system_prompt(dashboard_data, user, query_type)
            
            # Build messages with conversation history
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if available
            if conversation_history:
                for msg in conversation_history:
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            response = self.openai_client.chat.completions.create(
                model=getattr(settings, 'OPENAI_MODEL', 'gpt-4'),
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            return {
                'success': True,
                'response': ai_response,
                'model': response.model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to generate AI response'
            }
    
    def _classify_query(self, user_message: str) -> str:
        """Classify the type of query to determine what data to fetch"""
        message_lower = user_message.lower()
        
        # Case tracking keywords
        case_keywords = [
            'case', 'cases', 'case tracking', 'case status', 'case count', 'case number',
            'renewal case', 'renewal cases', 'case performance', 'case analysis',
            'case workflow', 'case process', 'case steps', 'case management',
            'pending case', 'completed case', 'overdue case', 'due case',
            'case assignment', 'case priority', 'case details', 'case history',
            'case report', 'case analytics', 'case insights', 'case data',
            'show case', 'list case', 'find case', 'search case',
            'case progress', 'case update', 'case timeline', 'case log'
        ]
        
        # Customer keywords
        customer_keywords = [
            'customer', 'customers', 'customer name', 'customer profile',
            'customer status', 'customer details', 'customer information',
            'customer contact', 'customer phone', 'customer email',
            'customer address', 'customer type', 'customer segment',
            'hni customer', 'normal customer', 'customer priority',
            'customer interaction', 'customer communication',
            'customer history', 'customer data', 'customer analytics',
            'first customer', 'last customer', 'specific customer',
            'individual customer', 'customer list', 'show customer',
            'find customer', 'search customer', 'customer by name'
        ]
        
        # Document keywords
        document_keywords = [
            'document', 'documents', 'document submission', 'document status',
            'submitted documents', 'document verification', 'document upload',
            'kyc documents', 'id proof', 'address proof', 'income proof',
            'pan card', 'aadhar card', 'passport', 'driving license',
            'voter id', 'bank statement', 'salary slip', 'form 16',
            'itr', 'tax document', 'business registration', 'medical report',
            'document verification', 'verified documents', 'pending documents',
            'document expiry', 'expired documents', 'document renewal'
        ]
        
        # Policy keywords
        policy_keywords = [
            'policy', 'policies', 'policy number', 'policy status',
            'policy details', 'policy information', 'policy type',
            'policy product', 'policy coverage', 'policy renewal',
            'policy expiry', 'policy premium', 'policy amount',
            'vehicle insurance', 'life insurance', 'health insurance',
            'term life', 'comprehensive', 'auto insurance',
            'renewed', 'renewed policies', 'recently renewed', 'policy renewals',
            'customers renewed', 'customers who renewed', 'how many renewed',
            'renewal status', 'renewal count', 'renewal statistics'
        ]
        
        # Payment keywords
        payment_keywords = [
            'payment', 'payments', 'payment status', 'payment amount',
            'renewal amount', 'premium payment', 'payment success',
            'payment failed', 'payment pending', 'payment collection',
            'outstanding amount', 'due amount', 'payment analytics'
        ]
        
        # Communication keywords
        communication_keywords = [
            'communication', 'contact', 'call', 'email', 'sms', 'whatsapp',
            'communication log', 'contact history', 'interaction',
            'communication status', 'delivery status', 'response rate',
            'communication effectiveness', 'contact attempts'
        ]
        
        # Non-case tracking keywords that should be declined
        non_case_tracking_keywords = [
            'weather', 'joke', 'cook', 'recipe', 'homework', 'capital', 'news', 'sports',
            'movie', 'music', 'game', 'travel', 'restaurant', 'shopping', 'fashion',
            'health', 'exercise', 'diet', 'medical', 'doctor', 'school', 'university',
            'politics', 'election', 'government', 'economy', 'stock', 'investment',
            'entertainment', 'celebrity', 'gossip', 'social media', 'facebook', 'instagram',
            'twitter', 'tiktok', 'youtube', 'netflix', 'amazon', 'google', 'apple',
            'microsoft', 'programming', 'coding', 'software', 'hardware', 'gaming',
            'sports', 'football', 'basketball', 'soccer', 'tennis', 'golf', 'baseball',
            'car', 'vehicle', 'automobile', 'house', 'home', 'real estate', 'rent',
            'buy', 'sell', 'price', 'cost', 'money', 'salary', 'job', 'career',
            'relationship', 'dating', 'marriage', 'family', 'children', 'parenting',
            'personal', 'private', 'life', 'lifestyle', 'hobby', 'interest', 'fun',
            'dna', 'biology', 'science', 'chemistry', 'physics', 'mathematics'
        ]
        
        # First check for non-case tracking keywords (higher priority)
        if any(keyword in message_lower for keyword in non_case_tracking_keywords):
            return 'non_case_tracking'
        
        # Check for renewal-specific questions (high priority)
        renewal_specific_keywords = ['renewed', 'renewal', 'renewed policies', 'recently renewed', 'customers renewed', 'how many renewed', 'renewal rate', 'renewal statistics']
        if any(keyword in message_lower for keyword in renewal_specific_keywords):
            return 'policy_analysis'
        
        # Check for policy-related questions (including renewal keywords)
        elif any(keyword in message_lower for keyword in policy_keywords):
            return 'policy_analysis'
        
        # Check for case-related questions
        elif any(keyword in message_lower for keyword in case_keywords):
            if any(keyword in message_lower for keyword in ['case performance', 'case analysis', 'case metrics']):
                return 'case_performance'
            elif any(keyword in message_lower for keyword in ['case workflow', 'case process', 'case steps']):
                return 'case_workflow'
            else:
                return 'case_general'
        
        # Check for individual customer questions (higher priority)
        elif any(keyword in message_lower for keyword in ['first customer', 'last customer', 'customer list', 'all customers', 'list customers', 'specific customer', 'individual customer']):
            return 'individual_customer'
        
        # Check for document-related questions (higher priority)
        elif any(keyword in message_lower for keyword in document_keywords):
            return 'document_analysis'
        
        # Check for customer-related questions
        elif any(keyword in message_lower for keyword in customer_keywords):
            return 'customer_analysis'
        
        # Check for payment-related questions
        elif any(keyword in message_lower for keyword in payment_keywords):
            return 'payment_analysis'
        
        # Check for communication-related questions
        elif any(keyword in message_lower for keyword in communication_keywords):
            return 'communication_analysis'
        
        # If none of the above, it's not related to case tracking
        else:
            return 'non_case_tracking'
    
    def _get_specialized_data(self, query_type: str, user_message: str) -> Dict[str, Any]:
        """Fetch specialized data based on query type"""
        try:
            if query_type == 'case_performance':
                return self._get_case_performance_data()
            elif query_type == 'case_workflow':
                return self._get_case_workflow_data()
            elif query_type == 'case_general':
                return self._get_case_general_data()
            elif query_type == 'customer_analysis':
                return self._get_customer_analysis_data()
            elif query_type == 'individual_customer':
                return self._get_individual_customer_data(user_message)
            elif query_type == 'document_analysis':
                return self._get_document_analysis_data(user_message)
            elif query_type == 'policy_analysis':
                return self._get_policy_analysis_data()
            elif query_type == 'payment_analysis':
                return self._get_payment_analysis_data()
            elif query_type == 'communication_analysis':
                return self._get_communication_analysis_data()
            elif query_type == 'non_case_tracking':
                return {'non_case_tracking': True}
            else:
                return {}
        except Exception as e:
            logger.error(f"Error fetching specialized data for {query_type}: {str(e)}")
            return {}
    
    def _get_case_performance_data(self) -> Dict[str, Any]:
        """Get detailed case performance data"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            
            # Get case performance by status
            cases = RenewalCase.objects.filter(is_deleted=False)
            
            status_performance = cases.values('status').annotate(
                count=Count('id'),
                avg_amount=Avg('renewal_amount'),
                total_amount=Sum('renewal_amount')
            )
            
            # Get case performance by time period
            time_performance = cases.filter(
                created_at__gte=thirty_days_ago
            ).values('status').annotate(
                count=Count('id'),
                success_rate=Count('id', filter=Q(status__in=['completed', 'renewed'])) * 100.0 / Count('id')
            )
            
            # Get case assignment performance
            assignment_performance = cases.filter(
                assigned_to__isnull=False
            ).values('assigned_to__first_name', 'assigned_to__last_name').annotate(
                assigned_count=Count('id'),
                completed_count=Count('id', filter=Q(status__in=['completed', 'renewed'])),
                success_rate=Count('id', filter=Q(status__in=['completed', 'renewed'])) * 100.0 / Count('id')
            )
            
            return {
                'case_performance': {
                    'status_performance': list(status_performance),
                    'time_performance': list(time_performance),
                    'assignment_performance': list(assignment_performance)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in case performance data: {str(e)}")
            return {'case_performance': {}}
    
    def _get_case_workflow_data(self) -> Dict[str, Any]:
        """Get case workflow data"""
        try:
            # Get case workflow stages
            cases = RenewalCase.objects.filter(is_deleted=False)
            
            workflow_stages = [
                {'stage': 'pending', 'count': cases.filter(status='pending').count()},
                {'stage': 'assigned', 'count': cases.filter(status='assigned').count()},
                {'stage': 'in_progress', 'count': cases.filter(status='in_progress').count()},
                {'stage': 'completed', 'count': cases.filter(status='completed').count()},
                {'stage': 'renewed', 'count': cases.filter(status='renewed').count()},
                {'stage': 'cancelled', 'count': cases.filter(status='cancelled').count()},
            ]
            
            # Get average processing time by status
            processing_times = cases.values('status').annotate(
                avg_days=Avg('updated_at') - Avg('created_at')
            )
            
            return {
                'case_workflow': {
                    'workflow_stages': workflow_stages,
                    'processing_times': list(processing_times)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in case workflow data: {str(e)}")
            return {'case_workflow': {}}
    
    def _get_case_general_data(self) -> Dict[str, Any]:
        """Get general case data"""
        try:
            # Get basic case statistics
            cases = RenewalCase.objects.filter(is_deleted=False)
            
            case_stats = {
                'total_cases': cases.count(),
                'pending_cases': cases.filter(status='pending').count(),
                'in_progress_cases': cases.filter(status='in_progress').count(),
                'completed_cases': cases.filter(status='completed').count(),
                'renewed_cases': cases.filter(status='renewed').count(),
            }
            
            # Get recent cases for examples
            recent_cases = cases.order_by('-created_at')[:5].values(
                'case_number', 'status', 'renewal_amount', 'customer__first_name', 
                'customer__last_name', 'policy__policy_number', 'created_at'
            )
            
            return {
                'case_general': {
                    'case_stats': case_stats,
                    'recent_cases': list(recent_cases)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in case general data: {str(e)}")
            return {'case_general': {}}
    
    def _get_customer_analysis_data(self) -> Dict[str, Any]:
        """Get customer analysis data"""
        try:
            # Get customer statistics
            customers = Customer.objects.filter(is_deleted=False)
            
            customer_analysis = {
                'total_customers': customers.count(),
                'profile_distribution': list(customers.values('profile').annotate(count=Count('id'))),
                'status_distribution': list(customers.values('status').annotate(count=Count('id'))),
                'type_distribution': list(customers.values('customer_type').annotate(count=Count('id'))),
            }
            
            # Get customer interaction stats
            interactions = customers.aggregate(
                total_interactions=Count('interactions'),
                avg_interactions_per_customer=Count('interactions') / Count('id') if customers.count() > 0 else 0
            )
            
            return {
                'customer_analysis': {
                    **customer_analysis,
                    'interactions': interactions
                }
            }
            
        except Exception as e:
            logger.error(f"Error in customer analysis data: {str(e)}")
            return {'customer_analysis': {}}
    
    def _get_individual_customer_data(self, user_message: str) -> Dict[str, Any]:
        """Get individual customer details based on the query"""
        try:
            customers = Customer.objects.filter(is_deleted=False)
            message_lower = user_message.lower()
            
            # Check for specific customer queries
            if 'first customer' in message_lower:
                # Get the first customer (by creation date)
                first_customer = customers.order_by('created_at').first()
                if first_customer:
                    return {
                        'individual_customer': {
                            'customer': {
                                'id': first_customer.id,
                                'customer_code': first_customer.customer_code,
                                'first_name': first_customer.first_name,
                                'last_name': first_customer.last_name,
                                'email': first_customer.email,
                                'phone': first_customer.phone,
                                'customer_type': first_customer.customer_type,
                                'status': first_customer.status,
                                'profile': first_customer.profile,
                                'created_at': first_customer.created_at,
                                'address_line1': first_customer.address_line1,
                                'city': first_customer.city,
                                'state': first_customer.state,
                                'postal_code': first_customer.postal_code,
                            },
                            'query_type': 'first_customer'
                        }
                    }
            
            elif 'last customer' in message_lower:
                # Get the last customer (by creation date)
                last_customer = customers.order_by('-created_at').first()
                if last_customer:
                    return {
                        'individual_customer': {
                            'customer': {
                                'id': last_customer.id,
                                'customer_code': last_customer.customer_code,
                                'first_name': last_customer.first_name,
                                'last_name': last_customer.last_name,
                                'email': last_customer.email,
                                'phone': last_customer.phone,
                                'customer_type': last_customer.customer_type,
                                'status': last_customer.status,
                                'profile': last_customer.profile,
                                'created_at': last_customer.created_at,
                                'address_line1': last_customer.address_line1,
                                'city': last_customer.city,
                                'state': last_customer.state,
                                'postal_code': last_customer.postal_code,
                            },
                            'query_type': 'last_customer'
                        }
                    }
            
            elif any(keyword in message_lower for keyword in ['customer list', 'all customers', 'list customers']):
                # Get list of all customers
                all_customers = customers.order_by('created_at').values(
                    'id', 'customer_code', 'first_name', 'last_name', 
                    'email', 'phone', 'customer_type', 'status', 'profile', 'created_at'
                )[:20]  # Limit to first 20 customers
                
                return {
                    'individual_customer': {
                        'customers': list(all_customers),
                        'query_type': 'customer_list',
                        'total_count': customers.count()
                    }
                }
            
            # If no specific query matched, return empty
            return {'individual_customer': {}}
            
        except Exception as e:
            logger.error(f"Error in individual customer data: {str(e)}")
            return {'individual_customer': {}}
    
    def _get_document_analysis_data(self, user_message: str) -> Dict[str, Any]:
        """Get customer document analysis data"""
        try:
            from apps.customers_documents.models import CustomerDocument
            
            message_lower = user_message.lower()
            
            # Try to find customer by name in the message
            customer = None
            if 'angela lee' in message_lower:
                try:
                    customer = Customer.objects.filter(
                        first_name__icontains='angela',
                        last_name__icontains='lee',
                        is_deleted=False
                    ).first()
                except:
                    pass
            
            document_analysis = {
                'total_documents': 0,
                'verified_documents': 0,
                'pending_documents': 0,
                'expired_documents': 0,
                'customer_documents': [],
                'document_types': [],
                'verification_status': {}
            }
            
            if customer:
                # Get documents from customers_documents model
                try:
                    documents = CustomerDocument.objects.filter(
                        customer=customer,
                        is_deleted=False
                    ).values(
                        'document_type', 'is_verified', 'verified_at',
                        'issue_date', 'expiry_date', 'issuing_authority',
                        'verification_notes', 'created_at'
                    )
                    
                    all_documents = list(documents)
                    
                    document_analysis['total_documents'] = len(all_documents)
                    document_analysis['verified_documents'] = len([d for d in all_documents if d.get('is_verified', False)])
                    document_analysis['pending_documents'] = len([d for d in all_documents if not d.get('is_verified', False)])
                    
                    # Check for expired documents
                    from datetime import date
                    today = date.today()
                    expired_count = 0
                    for doc in all_documents:
                        if doc.get('expiry_date') and doc['expiry_date'] < today:
                            expired_count += 1
                    document_analysis['expired_documents'] = expired_count
                    
                    # Get document types
                    document_types = {}
                    for doc in all_documents:
                        doc_type = doc.get('document_type', 'Unknown')
                        document_types[doc_type] = document_types.get(doc_type, 0) + 1
                    document_analysis['document_types'] = document_types
                    
                    # Get verification status
                    verification_status = {
                        'verified': document_analysis['verified_documents'],
                        'pending': document_analysis['pending_documents'],
                        'expired': document_analysis['expired_documents']
                    }
                    document_analysis['verification_status'] = verification_status
                    
                    # Customer-specific document details
                    document_analysis['customer_documents'] = all_documents[:10]  # Limit to 10 documents
                    document_analysis['customer_name'] = f"{customer.first_name} {customer.last_name}"
                    document_analysis['customer_code'] = customer.customer_code
                    
                except Exception as e:
                    logger.error(f"Error fetching documents for customer {customer.id}: {str(e)}")
                    document_analysis['error'] = f"Error fetching documents: {str(e)}"
            else:
                # If no specific customer found, get general document statistics
                try:
                    docs_count = CustomerDocument.objects.filter(is_deleted=False).count()
                    verified_count = CustomerDocument.objects.filter(is_deleted=False, is_verified=True).count()
                    
                    document_analysis['total_documents'] = docs_count
                    document_analysis['verified_documents'] = verified_count
                    document_analysis['pending_documents'] = document_analysis['total_documents'] - document_analysis['verified_documents']
                    
                except Exception as e:
                    logger.error(f"Error fetching general document statistics: {str(e)}")
                    document_analysis['error'] = f"Error fetching document statistics: {str(e)}"
            
            return {
                'document_analysis': document_analysis
            }
            
        except Exception as e:
            logger.error(f"Error in document analysis data: {str(e)}")
            return {'document_analysis': {}}
    
    def _get_policy_analysis_data(self) -> Dict[str, Any]:
        """Get policy analysis data"""
        try:
            # Get policy statistics from cases
            cases = RenewalCase.objects.filter(is_deleted=False)
            
            policy_analysis = {
                'total_policies': cases.count(),
                'policy_types': list(cases.values('policy__policy_type__name').annotate(count=Count('id'))),
                'policy_status_distribution': list(cases.values('status').annotate(count=Count('id'))),
                'renewed_policies': cases.filter(status='renewed').count(),
                'recently_renewed_customers': list(cases.filter(status='renewed').values(
                    'customer__first_name', 'customer__last_name', 'customer__phone',
                    'policy__policy_type__name', 'case_number', 'renewal_amount', 'created_at'
                ).order_by('-created_at')[:10]),
                'renewal_rate': (cases.filter(status='renewed').count() / cases.count() * 100) if cases.count() > 0 else 0,
            }
            
            return {
                'policy_analysis': policy_analysis
            }
            
        except Exception as e:
            logger.error(f"Error in policy analysis data: {str(e)}")
            return {'policy_analysis': {}}
    
    def _get_payment_analysis_data(self) -> Dict[str, Any]:
        """Get payment analysis data"""
        try:
            # Get payment statistics
            cases = RenewalCase.objects.filter(is_deleted=False)
            
            payment_analysis = {
                'total_amount': cases.aggregate(total=Sum('renewal_amount'))['total'] or 0,
                'pending_amount': cases.filter(payment_status='pending').aggregate(total=Sum('renewal_amount'))['total'] or 0,
                'success_amount': cases.filter(payment_status='success').aggregate(total=Sum('renewal_amount'))['total'] or 0,
                'failed_amount': cases.filter(payment_status='failed').aggregate(total=Sum('renewal_amount'))['total'] or 0,
                'payment_status_distribution': list(cases.values('payment_status').annotate(count=Count('id'), total_amount=Sum('renewal_amount'))),
            }
            
            return {
                'payment_analysis': payment_analysis
            }
            
        except Exception as e:
            logger.error(f"Error in payment analysis data: {str(e)}")
            return {'payment_analysis': {}}
    
    def _get_communication_analysis_data(self) -> Dict[str, Any]:
        """Get communication analysis data"""
        try:
            # Get communication statistics
            communications = CommunicationLog.objects.all()
            
            communication_analysis = {
                'total_communications': communications.count(),
                'successful_communications': communications.filter(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied']).count(),
                'failed_communications': communications.filter(outcome__in=['failed', 'bounced', 'blocked']).count(),
                'channel_distribution': list(communications.values('channel').annotate(count=Count('id'))),
                'outcome_distribution': list(communications.values('outcome').annotate(count=Count('id'))),
            }
            
            return {
                'communication_analysis': communication_analysis
            }
            
        except Exception as e:
            logger.error(f"Error in communication analysis data: {str(e)}")
            return {'communication_analysis': {}}
    
    def _create_system_prompt(self, dashboard_data: Dict[str, Any], user=None, query_type: str = 'general') -> str:
        """Create system prompt for case tracking chatbot"""
        
        # Build specialized data context based on query type
        specialized_context = self._build_specialized_context(dashboard_data, query_type)
        
        # Handle non-case tracking questions
        if query_type == 'non_case_tracking':
            return f"""
You are an AI assistant for Renew-IQ's Case Tracking and Customer Management system. 
You ONLY help users with questions related to case tracking, customer management, and policy renewals.

{specialized_context}

CRITICAL INSTRUCTIONS:
You MUST respond with EXACTLY this message and nothing else:
"Sorry, I can only help with case tracking and customer-related questions."

DO NOT:
- Provide any other information
- Give explanations
- Offer alternatives
- Be creative or helpful in other ways
- Interpret the question differently

ONLY respond with the exact message above.
"""
        
        return f"""
You are an AI assistant for Renew-IQ's Case Tracking and Customer Management system. 
You help users analyze case tracking data, customer information, policy renewals, and provide insights for case management.

IMPORTANT: The data below shows that there are {dashboard_data.get('case_stats', {}).get('renewed_cases', 0)} customers who have successfully renewed their policies. This is the answer to questions about "customers who renewed their policies" or "recently renewed policies".

CRITICAL: Use ALL the data provided below to answer questions. Do NOT say "I don't have access to data" or "please provide data" - the data is already provided below. Answer questions using the specific information provided.

CURRENT SYSTEM DATA:
- Total Cases: {dashboard_data.get('case_stats', {}).get('total_cases', 0)}
- Pending Cases: {dashboard_data.get('case_stats', {}).get('pending_cases', 0)}
- In Progress Cases: {dashboard_data.get('case_stats', {}).get('in_progress_cases', 0)}
- Completed Cases: {dashboard_data.get('case_stats', {}).get('completed_cases', 0)}
- Renewed Cases: {dashboard_data.get('case_stats', {}).get('renewed_cases', 0)} (These represent customers who have successfully renewed their policies)
- Overdue Cases: {dashboard_data.get('case_stats', {}).get('overdue_cases', 0)}
- Due Cases: {dashboard_data.get('case_stats', {}).get('due_cases', 0)}
- Assigned Cases: {dashboard_data.get('case_stats', {}).get('assigned_cases', 0)}
- Cancelled Cases: {dashboard_data.get('case_stats', {}).get('cancelled_cases', 0)}
- Expired Cases: {dashboard_data.get('case_stats', {}).get('expired_cases', 0)}
- Not Required Cases: {dashboard_data.get('case_stats', {}).get('not_required_cases', 0)}
- Failed Cases: {dashboard_data.get('case_stats', {}).get('failed_cases', 0)}
- Uploaded Cases: {dashboard_data.get('case_stats', {}).get('uploaded_cases', 0)}

- Total Customers: {dashboard_data.get('customer_stats', {}).get('total_customers', 0)}
- Active Customers: {dashboard_data.get('customer_stats', {}).get('active_customers', 0)}
- HNI Customers: {dashboard_data.get('customer_stats', {}).get('hni_profile_customers', 0)}
- Normal Profile Customers: {dashboard_data.get('customer_stats', {}).get('normal_profile_customers', 0)}

{specialized_context}

CRITICAL INSTRUCTIONS:
1. ALWAYS provide specific, data-driven insights based on the actual data provided above
2. Use exact numbers, percentages, and metrics from the database
3. Identify specific patterns, trends, and anomalies in the case tracking data
4. Provide actionable recommendations based on the actual data analysis
5. When discussing case performance, use the specific metrics provided
6. For customer analysis, focus on customer profiles, status distribution, and interaction patterns
6a. For individual customer queries, provide detailed information about specific customers including their contact details, status, and profile
6b. For document analysis queries, provide detailed information about customer document submission, verification status, and document types
7. For policy analysis, analyze policy types, renewal rates, and coverage patterns
8. IMPORTANT: When users ask about "renewed policies" or "customers who recently renewed", refer to cases with status 'renewed' - these represent successfully renewed policies. The specialized context below contains detailed renewal information including the number of renewed policies and customer details.
9. For payment analysis, examine payment status, collection rates, and outstanding amounts
10. For communication analysis, assess communication effectiveness and response rates
11. Always explain the "why" behind the data - what factors contribute to the current situation
12. Provide specific, measurable action items that can improve case management metrics
13. Use the specialized data sections to provide deep, contextual analysis
14. Never give generic advice - always tie recommendations to the specific data patterns observed
15. When asked about renewal statistics, always mention the specific number of renewed cases and renewal rate
16. CRITICAL: If you see "Renewed Cases: X" in the data above, this means X customers have successfully renewed their policies. Use this number when answering renewal questions.
17. DIRECT ANSWER: When asked "How many customers have renewed their policies?", the answer is the number shown in "Renewed Cases" above. Do NOT say "no data available" or "please provide data" - use the actual numbers provided.
18. INDIVIDUAL CUSTOMER DATA: When asked about specific customers (first customer, last customer, customer list), use the detailed customer information provided in the specialized context below. Do NOT say "I don't have access to customer data" - the data is provided below.

RESPONSE FORMAT:
- Start with key findings from the data
- Explain the significance of these findings
- Provide specific recommendations with expected impact
- Include actionable next steps
- Use data to support all claims and recommendations
"""
    
    def _build_specialized_context(self, dashboard_data: Dict[str, Any], query_type: str) -> str:
        """Build specialized context based on query type"""
        if query_type == 'case_performance':
            return self._build_case_performance_context(dashboard_data.get('case_performance', {}))
        elif query_type == 'case_workflow':
            return self._build_case_workflow_context(dashboard_data.get('case_workflow', {}))
        elif query_type == 'case_general':
            return self._build_case_general_context(dashboard_data.get('case_general', {}))
        elif query_type == 'customer_analysis':
            return self._build_customer_analysis_context(dashboard_data.get('customer_analysis', {}))
        elif query_type == 'individual_customer':
            return self._build_individual_customer_context(dashboard_data.get('individual_customer', {}))
        elif query_type == 'document_analysis':
            return self._build_document_analysis_context(dashboard_data.get('document_analysis', {}))
        elif query_type == 'policy_analysis':
            return self._build_policy_analysis_context(dashboard_data.get('policy_analysis', {}))
        elif query_type == 'payment_analysis':
            return self._build_payment_analysis_context(dashboard_data.get('payment_analysis', {}))
        elif query_type == 'communication_analysis':
            return self._build_communication_analysis_context(dashboard_data.get('communication_analysis', {}))
        elif query_type == 'non_case_tracking':
            return self._build_non_case_tracking_context()
        else:
            return ""
    
    def _build_case_performance_context(self, case_data: Dict[str, Any]) -> str:
        """Build context for case performance analysis"""
        if not case_data:
            return ""
        
        context = "\n\nCASE PERFORMANCE ANALYSIS:\n"
        
        # Status performance
        status_performance = case_data.get('status_performance', [])
        if status_performance:
            context += "\nCASE STATUS PERFORMANCE:\n"
            for status in status_performance:
                context += f"- {status.get('status', 'Unknown')}: {status.get('count', 0)} cases (Avg Amount: ₹{status.get('avg_amount', 0):.2f}, Total: ₹{status.get('total_amount', 0):.2f})\n"
        
        # Time performance
        time_performance = case_data.get('time_performance', [])
        if time_performance:
            context += "\nCASE PERFORMANCE (30 days):\n"
            for time_data in time_performance:
                context += f"- {time_data.get('status', 'Unknown')}: {time_data.get('count', 0)} cases, {time_data.get('success_rate', 0):.1f}% success rate\n"
        
        # Assignment performance
        assignment_performance = case_data.get('assignment_performance', [])
        if assignment_performance:
            context += "\nASSIGNMENT PERFORMANCE:\n"
            for assignment in assignment_performance:
                context += f"- {assignment.get('assigned_to__first_name', 'Unknown')} {assignment.get('assigned_to__last_name', '')}: {assignment.get('assigned_count', 0)} assigned, {assignment.get('completed_count', 0)} completed, {assignment.get('success_rate', 0):.1f}% success rate\n"
        
        return context
    
    def _build_case_workflow_context(self, workflow_data: Dict[str, Any]) -> str:
        """Build context for case workflow"""
        if not workflow_data:
            return ""
        
        context = "\n\nCASE WORKFLOW ANALYSIS:\n"
        
        # Workflow stages
        workflow_stages = workflow_data.get('workflow_stages', [])
        if workflow_stages:
            context += "\nCASE WORKFLOW STAGES:\n"
            for stage in workflow_stages:
                context += f"- {stage.get('stage', 'Unknown')}: {stage.get('count', 0)} cases\n"
        
        return context
    
    def _build_case_general_context(self, case_data: Dict[str, Any]) -> str:
        """Build context for general case questions"""
        if not case_data:
            return ""
        
        context = "\n\nCASE INFORMATION:\n"
        
        # Case stats
        case_stats = case_data.get('case_stats', {})
        if case_stats:
            context += "\nCURRENT CASE STATISTICS:\n"
            context += f"- Total Cases: {case_stats.get('total_cases', 0)}\n"
            context += f"- Pending Cases: {case_stats.get('pending_cases', 0)}\n"
            context += f"- In Progress Cases: {case_stats.get('in_progress_cases', 0)}\n"
            context += f"- Completed Cases: {case_stats.get('completed_cases', 0)}\n"
            context += f"- Renewed Cases: {case_stats.get('renewed_cases', 0)}\n"
            context += f"- Due Cases: {case_stats.get('due_cases', 0)}\n"
            context += f"- Overdue Cases: {case_stats.get('overdue_cases', 0)}\n"
            context += f"- Assigned Cases: {case_stats.get('assigned_cases', 0)}\n"
            context += f"- Cancelled Cases: {case_stats.get('cancelled_cases', 0)}\n"
            context += f"- Expired Cases: {case_stats.get('expired_cases', 0)}\n"
            context += f"- Not Required Cases: {case_stats.get('not_required_cases', 0)}\n"
            context += f"- Failed Cases: {case_stats.get('failed_cases', 0)}\n"
            context += f"- Uploaded Cases: {case_stats.get('uploaded_cases', 0)}\n"
        
        # Recent cases
        recent_cases = case_data.get('recent_cases', [])
        if recent_cases:
            context += "\nRECENT CASES:\n"
            for case in recent_cases:
                context += f"- {case.get('case_number', 'Unknown')}: {case.get('customer__first_name', '')} {case.get('customer__last_name', '')} ({case.get('status', 'Unknown')})\n"
                context += f"  Policy: {case.get('policy__policy_number', 'Unknown')}, Amount: ₹{case.get('renewal_amount', 0):.2f}\n"
        
        return context
    
    def _build_customer_analysis_context(self, customer_data: Dict[str, Any]) -> str:
        """Build context for customer analysis"""
        if not customer_data:
            return ""
        
        context = "\n\nCUSTOMER ANALYSIS:\n"
        
        # Profile distribution
        profile_distribution = customer_data.get('profile_distribution', [])
        if profile_distribution:
            context += "\nCUSTOMER PROFILE DISTRIBUTION:\n"
            for profile in profile_distribution:
                context += f"- {profile.get('profile', 'Unknown')}: {profile.get('count', 0)} customers\n"
        
        # Status distribution
        status_distribution = customer_data.get('status_distribution', [])
        if status_distribution:
            context += "\nCUSTOMER STATUS DISTRIBUTION:\n"
            for status in status_distribution:
                context += f"- {status.get('status', 'Unknown')}: {status.get('count', 0)} customers\n"
        
        return context
    
    def _build_individual_customer_context(self, customer_data: Dict[str, Any]) -> str:
        """Build context for individual customer queries"""
        if not customer_data:
            return ""
        
        context = "\n\nINDIVIDUAL CUSTOMER INFORMATION:\n"
        
        query_type = customer_data.get('query_type', '')
        
        if query_type == 'first_customer':
            customer = customer_data.get('customer', {})
            if customer:
                context += f"FIRST CUSTOMER DETAILS:\n"
                context += f"- Customer Code: {customer.get('customer_code', 'N/A')}\n"
                context += f"- Name: {customer.get('first_name', '')} {customer.get('last_name', '')}\n"
                context += f"- Email: {customer.get('email', 'N/A')}\n"
                context += f"- Phone: {customer.get('phone', 'N/A')}\n"
                context += f"- Customer Type: {customer.get('customer_type', 'N/A')}\n"
                context += f"- Status: {customer.get('status', 'N/A')}\n"
                context += f"- Profile: {customer.get('profile', 'N/A')}\n"
                context += f"- Created: {customer.get('created_at', 'N/A')}\n"
                if customer.get('address_line1'):
                    context += f"- Address: {customer.get('address_line1', '')}, {customer.get('city', '')}, {customer.get('state', '')} - {customer.get('postal_code', '')}\n"
        
        elif query_type == 'last_customer':
            customer = customer_data.get('customer', {})
            if customer:
                context += f"LAST CUSTOMER DETAILS:\n"
                context += f"- Customer Code: {customer.get('customer_code', 'N/A')}\n"
                context += f"- Name: {customer.get('first_name', '')} {customer.get('last_name', '')}\n"
                context += f"- Email: {customer.get('email', 'N/A')}\n"
                context += f"- Phone: {customer.get('phone', 'N/A')}\n"
                context += f"- Customer Type: {customer.get('customer_type', 'N/A')}\n"
                context += f"- Status: {customer.get('status', 'N/A')}\n"
                context += f"- Profile: {customer.get('profile', 'N/A')}\n"
                context += f"- Created: {customer.get('created_at', 'N/A')}\n"
                if customer.get('address_line1'):
                    context += f"- Address: {customer.get('address_line1', '')}, {customer.get('city', '')}, {customer.get('state', '')} - {customer.get('postal_code', '')}\n"
        
        elif query_type == 'customer_list':
            customers = customer_data.get('customers', [])
            total_count = customer_data.get('total_count', 0)
            if customers:
                context += f"ALL CUSTOMERS LIST (Total: {total_count}):\n"
                for i, customer in enumerate(customers, 1):
                    context += f"{i}. {customer.get('first_name', '')} {customer.get('last_name', '')} "
                    context += f"(Code: {customer.get('customer_code', 'N/A')}, "
                    context += f"Email: {customer.get('email', 'N/A')}, "
                    context += f"Phone: {customer.get('phone', 'N/A')}, "
                    context += f"Type: {customer.get('customer_type', 'N/A')}, "
                    context += f"Status: {customer.get('status', 'N/A')}, "
                    context += f"Profile: {customer.get('profile', 'N/A')})\n"
        
        return context
    
    def _build_document_analysis_context(self, document_data: Dict[str, Any]) -> str:
        """Build context for document analysis"""
        if not document_data:
            return ""
        
        context = "\n\nDOCUMENT ANALYSIS:\n"
        
        # Basic document statistics
        context += f"TOTAL DOCUMENTS: {document_data.get('total_documents', 0)}\n"
        context += f"VERIFIED DOCUMENTS: {document_data.get('verified_documents', 0)}\n"
        context += f"PENDING DOCUMENTS: {document_data.get('pending_documents', 0)}\n"
        context += f"EXPIRED DOCUMENTS: {document_data.get('expired_documents', 0)}\n"
        
        # Customer-specific information
        if document_data.get('customer_name'):
            context += f"\nCUSTOMER: {document_data.get('customer_name', 'Unknown')} (Code: {document_data.get('customer_code', 'N/A')})\n"
        
        # Document types
        document_types = document_data.get('document_types', {})
        if document_types:
            context += "\nDOCUMENT TYPES:\n"
            for doc_type, count in document_types.items():
                context += f"- {doc_type}: {count} documents\n"
        
        # Verification status
        verification_status = document_data.get('verification_status', {})
        if verification_status:
            context += "\nVERIFICATION STATUS:\n"
            context += f"- Verified: {verification_status.get('verified', 0)} documents\n"
            context += f"- Pending: {verification_status.get('pending', 0)} documents\n"
            context += f"- Expired: {verification_status.get('expired', 0)} documents\n"
        
        # Individual documents
        customer_documents = document_data.get('customer_documents', [])
        if customer_documents:
            context += "\nDOCUMENT DETAILS:\n"
            for i, doc in enumerate(customer_documents, 1):
                context += f"{i}. {doc.get('document_type', 'Unknown')} "
                context += f"(Verified: {'Yes' if doc.get('is_verified', False) else 'No'})"
                if doc.get('verified_at'):
                    context += f" - Verified on: {doc.get('verified_at')}"
                if doc.get('expiry_date'):
                    context += f" - Expires: {doc.get('expiry_date')}"
                context += "\n"
        
        # Error information
        if document_data.get('error'):
            context += f"\nERROR: {document_data.get('error')}\n"
        
        return context
    
    def _build_policy_analysis_context(self, policy_data: Dict[str, Any]) -> str:
        """Build context for policy analysis"""
        if not policy_data:
            return ""
        
        context = "\n\nPOLICY ANALYSIS:\n"
        
        # Basic policy statistics
        context += f"TOTAL POLICIES: {policy_data.get('total_policies', 0)}\n"
        context += f"RENEWED POLICIES: {policy_data.get('renewed_policies', 0)}\n"
        context += f"RENEWAL RATE: {policy_data.get('renewal_rate', 0):.1f}%\n"
        
        # Policy types
        policy_types = policy_data.get('policy_types', [])
        if policy_types:
            context += "\nPOLICY TYPES:\n"
            for policy_type in policy_types:
                context += f"- {policy_type.get('policy__policy_type__name', 'Unknown')}: {policy_type.get('count', 0)} policies\n"
        
        # Policy status distribution
        policy_status_dist = policy_data.get('policy_status_distribution', [])
        if policy_status_dist:
            context += "\nPOLICY STATUS DISTRIBUTION:\n"
            for status in policy_status_dist:
                context += f"- {status.get('status', 'Unknown')}: {status.get('count', 0)} policies\n"
        
        # Recently renewed customers
        recently_renewed = policy_data.get('recently_renewed_customers', [])
        if recently_renewed:
            context += "\nRECENTLY RENEWED CUSTOMERS:\n"
            for customer in recently_renewed:
                context += f"- {customer.get('customer__first_name', '')} {customer.get('customer__last_name', 'Unknown')} "
                context += f"(Case: {customer.get('case_number', 'Unknown')}, "
                context += f"Policy: {customer.get('policy__policy_type__name', 'Unknown')}, "
                context += f"Amount: ₹{customer.get('renewal_amount', 0):.2f})\n"
        
        return context
    
    def _build_payment_analysis_context(self, payment_data: Dict[str, Any]) -> str:
        """Build context for payment analysis"""
        if not payment_data:
            return ""
        
        context = "\n\nPAYMENT ANALYSIS:\n"
        
        context += f"TOTAL AMOUNT: ₹{payment_data.get('total_amount', 0):.2f}\n"
        context += f"PENDING AMOUNT: ₹{payment_data.get('pending_amount', 0):.2f}\n"
        context += f"SUCCESS AMOUNT: ₹{payment_data.get('success_amount', 0):.2f}\n"
        context += f"FAILED AMOUNT: ₹{payment_data.get('failed_amount', 0):.2f}\n"
        
        # Payment status distribution
        payment_status_dist = payment_data.get('payment_status_distribution', [])
        if payment_status_dist:
            context += "\nPAYMENT STATUS DISTRIBUTION:\n"
            for status in payment_status_dist:
                context += f"- {status.get('payment_status', 'Unknown')}: {status.get('count', 0)} cases, ₹{status.get('total_amount', 0):.2f}\n"
        
        return context
    
    def _build_communication_analysis_context(self, comm_data: Dict[str, Any]) -> str:
        """Build context for communication analysis"""
        if not comm_data:
            return ""
        
        context = "\n\nCOMMUNICATION ANALYSIS:\n"
        
        context += f"TOTAL COMMUNICATIONS: {comm_data.get('total_communications', 0)}\n"
        context += f"SUCCESSFUL COMMUNICATIONS: {comm_data.get('successful_communications', 0)}\n"
        context += f"FAILED COMMUNICATIONS: {comm_data.get('failed_communications', 0)}\n"
        
        # Channel distribution
        channel_dist = comm_data.get('channel_distribution', [])
        if channel_dist:
            context += "\nCOMMUNICATION CHANNELS:\n"
            for channel in channel_dist:
                context += f"- {channel.get('channel', 'Unknown')}: {channel.get('count', 0)} communications\n"
        
        return context
    
    def _build_non_case_tracking_context(self) -> str:
        """Build context for non-case tracking questions"""
        return "\n\nIMPORTANT: This question is not related to case tracking or customer management. Please respond with the standard non-case tracking message."
    
    def get_quick_suggestions(self) -> List[Dict[str, str]]:
        """Get quick suggestions for case tracking queries"""
        return [
            {
                "id": "analyze_case_performance",
                "title": "Analyze my current case performance",
                "description": "Get insights on case status, completion rates, and processing efficiency"
            },
            {
                "id": "customer_analysis",
                "title": "What's my customer profile distribution?",
                "description": "Analyze customer profiles, status distribution, and segmentation"
            },
            {
                "id": "case_workflow",
                "title": "Explain the case tracking workflow",
                "description": "Understand the case management process and workflow stages"
            },
            {
                "id": "payment_analysis",
                "title": "Show me payment collection status",
                "description": "Analyze payment status, outstanding amounts, and collection rates"
            },
            {
                "id": "communication_effectiveness",
                "title": "How effective are my customer communications?",
                "description": "Analyze communication channels, response rates, and engagement"
            },
            {
                "id": "overdue_cases",
                "title": "How many overdue cases do I have?",
                "description": "Get details on overdue cases and priority actions needed"
            }
        ]


def get_case_tracking_chatbot_service():
    """Get the case tracking chatbot service instance"""
    return CaseTrackingChatbotService()
