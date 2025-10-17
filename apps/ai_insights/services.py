import logging
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from django.contrib.auth import get_user_model

# OpenAI imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

from apps.renewals.models import RenewalCase
from apps.customer_payments.models import CustomerPayment
from apps.campaigns.models import Campaign
from apps.customers.models import Customer
from apps.policies.models import Policy

User = get_user_model()
logger = logging.getLogger(__name__)


class AIService:
    
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
        return (
            OPENAI_AVAILABLE and 
            self.openai_client is not None and 
            bool(getattr(settings, 'OPENAI_API_KEY', ''))
        )
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        try:
            renewal_cases = RenewalCase.objects.filter(is_deleted=False)
            
            renewal_stats = {
                'total_cases': renewal_cases.count(),
                'in_progress': renewal_cases.filter(status='in_progress').count(),
                'renewed': renewal_cases.filter(status='renewed').count(),
                'pending_action': renewal_cases.filter(status='pending_action').count(),
                'failed': renewal_cases.filter(status='failed').count(),
                'total_renewal_amount': float(renewal_cases.aggregate(
                    total=Sum('renewal_amount')
                )['total'] or 0),
            }
            
            payments = CustomerPayment.objects.filter(is_deleted=False)
            payment_stats = {
                'total_payments': payments.count(),
                'completed_payments': payments.filter(payment_status='completed').count(),
                'pending_payments': payments.filter(payment_status='pending').count(),
                'failed_payments': payments.filter(payment_status='failed').count(),
                'total_collected': float(payments.filter(
                    payment_status='completed'
                ).aggregate(total=Sum('payment_amount'))['total'] or 0),
            }
            
            campaigns = Campaign.objects.filter(is_deleted=False)
            campaign_stats = {
                'total_campaigns': campaigns.count(),
                'active_campaigns': campaigns.filter(status='active').count(),
                'completed_campaigns': campaigns.filter(status='completed').count(),
                'scheduled_campaigns': campaigns.filter(status='scheduled').count(),
            }
            
            customers = Customer.objects.filter(is_deleted=False)
            customer_stats = {
                'total_customers': customers.count(),
                'active_customers': customers.filter(status='active').count(),
                'verified_customers': customers.filter(
                    Q(email_verified=True) | Q(phone_verified=True) | Q(pan_verified=True)
                ).count(),
            }
            
            policies = Policy.objects.filter(is_deleted=False)
            policy_stats = {
                'total_policies': policies.count(),
                'active_policies': policies.filter(status='active').count(),
                'expired_policies': policies.filter(status='expired').count(),
                'renewed_policies': policies.filter(status='renewed').count(),
            }
            
            from datetime import datetime, timedelta
            today = datetime.now().date()
            
            expiring_soon = policies.filter(
                end_date__gte=today,
                end_date__lte=today + timedelta(days=30),
                status='active'
            ).select_related('customer', 'policy_type')
            
            recent_renewals = RenewalCase.objects.filter(
                is_deleted=False,
                status='renewed',
                created_at__gte=timezone.now() - timedelta(days=30)
            ).select_related('policy', 'customer')
            
            sample_policies = policies.filter(status='active')[:5].select_related('customer', 'policy_type')
            
            detailed_policy_info = []
            for policy in sample_policies:
                detailed_policy_info.append({
                    'policy_number': policy.policy_number,
                    'customer_name': policy.customer.full_name if policy.customer else 'Unknown',
                    'policy_type': policy.policy_type.name if policy.policy_type else 'Unknown',
                    'start_date': policy.start_date.strftime('%Y-%m-%d') if policy.start_date else None,
                    'end_date': policy.end_date.strftime('%Y-%m-%d') if policy.end_date else None,
                    'renewal_date': policy.renewal_date.strftime('%Y-%m-%d') if policy.renewal_date else None,
                    'premium_amount': float(policy.premium_amount) if policy.premium_amount else 0,
                    'sum_assured': float(policy.sum_assured) if policy.sum_assured else 0,
                    'status': policy.status,
                    'payment_frequency': policy.payment_frequency,
                })
            
            expiring_policies_info = []
            for policy in expiring_soon:
                days_until_expiry = (policy.end_date - today).days
                expiring_policies_info.append({
                    'policy_number': policy.policy_number,
                    'customer_name': policy.customer.full_name if policy.customer else 'Unknown',
                    'end_date': policy.end_date.strftime('%Y-%m-%d'),
                    'days_until_expiry': days_until_expiry,
                    'premium_amount': float(policy.premium_amount) if policy.premium_amount else 0,
                })
            
            return {
                'renewal_cases': renewal_stats,
                'payments': payment_stats,
                'campaigns': campaign_stats,
                'customers': customer_stats,
                'policies': policy_stats,
                'detailed_policies': detailed_policy_info,
                'expiring_soon': expiring_policies_info,
                'recent_renewals_count': recent_renewals.count(),
                'timestamp': timezone.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error fetching dashboard data: {str(e)}")
            return {}
    
    def generate_ai_response(self, user_message: str, context_data: Dict[str, Any] = None, user=None, conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not available',
                'message': 'OpenAI API key not configured or service unavailable'
            }
        
        try:
            query_type = self._classify_query(user_message)
         
            dashboard_data = self.get_dashboard_data()
            specialized_data = self._get_specialized_data(query_type, user_message)
            dashboard_data.update(specialized_data)
            
            if user:
                user_specific_data = self._get_user_specific_data(user)
                dashboard_data['user_specific'] = user_specific_data
            
            system_prompt = self._create_system_prompt(dashboard_data, user, query_type)
            
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                for msg in conversation_history:
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            messages.append({"role": "user", "content": user_message})
            
            response = self.openai_client.chat.completions.create(
                model=getattr(settings, 'OPENAI_MODEL', 'gpt-4'),
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            ai_response = response.choices[0].message.content
            
            return {
                'success': True,
                'response': ai_response,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                } if response.usage else None,
                'model': response.model,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to generate AI response'
            }
    
    def _get_user_specific_data(self, user) -> Dict[str, Any]:
        """Get user-specific policy and customer data"""
        try:
            from apps.customers.models import Customer
            
            customer = None
            try:
                customer = Customer.objects.filter(
                    email=user.email,
                    status='active'
                ).first()
                logger.info(f"Customer lookup by email '{user.email}': {'Found' if customer else 'Not found'}")
            except Exception as e:
                logger.error(f"Error in customer lookup by email: {str(e)}")
            
            if not customer and user.first_name and user.last_name:
                try:
                    customer = Customer.objects.filter(
                        first_name__icontains=user.first_name,
                        last_name__icontains=user.last_name,
                        status='active'
                    ).first()
                    logger.info(f"Customer lookup by name '{user.first_name} {user.last_name}': {'Found' if customer else 'Not found'}")
                except Exception as e:
                    logger.error(f"Error in customer lookup by name: {str(e)}")
            
            if not customer and user.first_name:
                try:
                    customer = Customer.objects.filter(
                        first_name__icontains=user.first_name,
                        status='active'
                    ).first()
                    logger.info(f"Customer lookup by first name '{user.first_name}': {'Found' if customer else 'Not found'}")
                except Exception as e:
                    logger.error(f"Error in customer lookup by first name: {str(e)}")
            
            user_policies = []
            user_renewal_cases = []
            
            if customer:
                user_policies = Policy.objects.filter(
                    customer=customer,
                    is_deleted=False
                ).select_related('policy_type').order_by('-end_date')
                
                user_renewal_cases = RenewalCase.objects.filter(
                    customer=customer,
                    is_deleted=False
                ).select_related('policy').order_by('-created_at')
                
                formatted_policies = []
                for policy in user_policies:
                    policy_data = {
                        'policy_number': policy.policy_number,
                        'policy_type': policy.policy_type.name if policy.policy_type else 'Unknown',
                        'policy_type_code': policy.policy_type.code if policy.policy_type else 'Unknown',
                        'start_date': policy.start_date.strftime('%Y-%m-%d') if policy.start_date else None,
                        'end_date': policy.end_date.strftime('%Y-%m-%d') if policy.end_date else None,
                        'renewal_date': policy.renewal_date.strftime('%Y-%m-%d') if policy.renewal_date else None,
                        'premium_amount': float(policy.premium_amount) if policy.premium_amount else 0,
                        'sum_assured': float(policy.sum_assured) if policy.sum_assured else 0,
                        'status': policy.status,
                        'payment_frequency': policy.payment_frequency,
                    }
                    
                    if policy.policy_type:
                        from apps.policy_coverages.models import PolicyCoverage
                        coverages = PolicyCoverage.objects.filter(
                            policy_type=policy.policy_type,
                            is_deleted=False
                        ).order_by('display_order')
                        
                        coverage_list = []
                        for coverage in coverages:
                            coverage_list.append({
                                'name': coverage.coverage_name,
                                'description': coverage.coverage_description,
                                'type': coverage.coverage_type,
                                'category': coverage.coverage_category,
                                'amount': float(coverage.coverage_amount) if coverage.coverage_amount else 0,
                                'is_included': coverage.is_included,
                                'is_optional': coverage.is_optional,
                                'premium_impact': float(coverage.premium_impact) if coverage.premium_impact else 0,
                                'terms_conditions': coverage.terms_conditions,
                            })
                        
                        from apps.policy_features.models import PolicyFeature
                        features = PolicyFeature.objects.filter(
                            policy_type=policy.policy_type,
                            is_deleted=False
                        ).order_by('display_order')
                        
                        feature_list = []
                        for feature in features:
                            feature_list.append({
                                'name': feature.feature_name,
                                'description': feature.feature_description,
                                'type': feature.feature_type,
                                'value': feature.feature_value,
                                'is_mandatory': feature.is_mandatory,
                            })
                        
                        from apps.policy_additional_benefits.models import PolicyAdditionalBenefit
                        additional_benefits = PolicyAdditionalBenefit.objects.filter(
                            policy_coverages__policy_type=policy.policy_type,
                            is_deleted=False,
                            is_active=True
                        ).select_related('policy_coverages').order_by('display_order')
                        
                        benefit_list = []
                        for benefit in additional_benefits:
                            benefit_list.append({
                                'name': benefit.benefit_name,
                                'description': benefit.benefit_description,
                                'type': benefit.benefit_type,
                                'category': benefit.benefit_category,
                                'value': benefit.benefit_value,
                                'coverage_amount': float(benefit.coverage_amount) if benefit.coverage_amount else 0,
                                'is_optional': benefit.is_optional,
                                'premium_impact': float(benefit.premium_impact) if benefit.premium_impact else 0,
                                'terms_conditions': benefit.terms_conditions,
                            })
                        
                        policy_data['coverages'] = coverage_list
                        policy_data['features'] = feature_list
                        policy_data['additional_benefits'] = benefit_list
                    
                    formatted_policies.append(policy_data)
                
                formatted_renewals = []
                for renewal in user_renewal_cases:
                    formatted_renewals.append({
                        'case_number': renewal.case_number,
                        'policy_number': renewal.policy.policy_number if renewal.policy else 'Unknown',
                        'status': renewal.status,
                        'renewal_amount': float(renewal.renewal_amount) if renewal.renewal_amount else 0,
                        'created_at': renewal.created_at.strftime('%Y-%m-%d') if renewal.created_at else None,
                    })
                
                return {
                    'customer_found': True,
                    'customer_name': customer.full_name,
                    'customer_email': customer.email,
                    'customer_phone': customer.phone,
                    'policies': formatted_policies,
                    'renewal_cases': formatted_renewals,
                    'total_policies': len(formatted_policies),
                    'active_policies': len([p for p in formatted_policies if p['status'] == 'active']),
                }
            else:
                return {
                    'customer_found': False,
                    'user_email': user.email,
                    'user_name': user.full_name,
                    'policies': [],
                    'renewal_cases': [],
                    'total_policies': 0,
                    'active_policies': 0,
                }
                
        except Exception as e:
            logger.error(f"Error getting user-specific data: {str(e)}")
            return {
                'customer_found': False,
                'error': str(e),
                'policies': [],
                'renewal_cases': [],
                'total_policies': 0,
                'active_policies': 0,
            }
    
    def _create_system_prompt(self, dashboard_data: Dict[str, Any], user=None, query_type: str = 'general') -> str:
        
        detailed_policies = dashboard_data.get('detailed_policies', [])
        expiring_policies = dashboard_data.get('expiring_soon', [])
        user_specific = dashboard_data.get('user_specific', {})
        
        user_info_text = ""
        if user and user_specific:
            if user_specific.get('customer_found'):
                user_info_text = f"\n\nCURRENT USER INFORMATION:\n"
                user_info_text += f"Customer Name: {user_specific.get('customer_name')}\n"
                user_info_text += f"Email: {user_specific.get('customer_email')}\n"
                user_info_text += f"Phone: {user_specific.get('customer_phone')}\n"
                user_info_text += f"Total Policies: {user_specific.get('total_policies', 0)}\n"
                user_info_text += f"Active Policies: {user_specific.get('active_policies', 0)}\n\n"
                
                user_policies = user_specific.get('policies', [])
                if user_policies:
                    user_info_text += "YOUR POLICIES:\n"
                    for policy in user_policies:
                        user_info_text += f"- Policy: {policy['policy_number']} | Type: {policy['policy_type']}\n"
                        user_info_text += f"  Start: {policy['start_date']} | End: {policy['end_date']} | Renewal: {policy['renewal_date'] or 'Not set'}\n"
                        user_info_text += f"  Premium: ₹{policy['premium_amount']:,.2f} | Sum Assured: ₹{policy['sum_assured']:,.2f} | Status: {policy['status']}\n"
                        
                        coverages = policy.get('coverages', [])
                        if coverages:
                            user_info_text += f"  COVERAGES:\n"
                            for coverage in coverages:
                                user_info_text += f"    • {coverage['name']}: {coverage['description']}\n"
                                if coverage['amount'] > 0:
                                    user_info_text += f"      Coverage Amount: ₹{coverage['amount']:,.2f}\n"
                                if coverage['is_optional']:
                                    user_info_text += f"      Optional (Premium Impact: ₹{coverage['premium_impact']:,.2f})\n"
                        
                        features = policy.get('features', [])
                        if features:
                            user_info_text += f"  FEATURES:\n"
                            for feature in features:
                                user_info_text += f"    • {feature['name']}: {feature['description']}\n"
                                if feature['value']:
                                    user_info_text += f"      Value: {feature['value']}\n"
                        
                        benefits = policy.get('additional_benefits', [])
                        if benefits:
                            user_info_text += f"  ADDITIONAL BENEFITS:\n"
                            for benefit in benefits:
                                user_info_text += f"    • {benefit['name']}: {benefit['description']}\n"
                                if benefit['coverage_amount'] > 0:
                                    user_info_text += f"      Coverage: ₹{benefit['coverage_amount']:,.2f}\n"
                                if benefit['is_optional']:
                                    user_info_text += f"      Optional (Premium Impact: ₹{benefit['premium_impact']:,.2f})\n"
                        
                        user_info_text += "\n"
                else:
                    user_info_text += "YOUR POLICIES: No policies found for this customer.\n\n"
                
                user_renewals = user_specific.get('renewal_cases', [])
                if user_renewals:
                    user_info_text += "YOUR RENEWAL CASES:\n"
                    for renewal in user_renewals:
                        user_info_text += f"- Case: {renewal['case_number']} | Policy: {renewal['policy_number']} | Status: {renewal['status']}\n"
                        user_info_text += f"  Amount: ₹{renewal['renewal_amount']:,.2f} | Date: {renewal['created_at']}\n\n"
            else:
                user_info_text = f"\n\nCURRENT USER INFORMATION:\n"
                user_info_text += f"User: {user_specific.get('user_name', 'Unknown')}\n"
                user_info_text += f"Email: {user_specific.get('user_email', 'Unknown')}\n"
                user_info_text += f"Customer Record: Not found in system\n"
                user_info_text += f"Policies: No policies found for this user\n\n"
        
        policy_details_text = ""
        if detailed_policies:
            policy_details_text = "\n\nGENERAL POLICY INFORMATION (All Policies):\n"
            for policy in detailed_policies:
                policy_details_text += f"- Policy: {policy['policy_number']} | Customer: {policy['customer_name']} | Type: {policy['policy_type']}\n"
                policy_details_text += f"  Start: {policy['start_date']} | End: {policy['end_date']} | Renewal: {policy['renewal_date'] or 'Not set'}\n"
                policy_details_text += f"  Premium: ₹{policy['premium_amount']:,.2f} | Sum Assured: ₹{policy['sum_assured']:,.2f} | Status: {policy['status']}\n\n"
        
        expiring_text = ""
        if expiring_policies:
            expiring_text = "\n\nPOLICIES EXPIRING SOON (within 30 days):\n"
            for policy in expiring_policies:
                expiring_text += f"- Policy: {policy['policy_number']} | Customer: {policy['customer_name']} | Expires: {policy['end_date']} ({policy['days_until_expiry']} days)\n"
                expiring_text += f"  Premium: ₹{policy['premium_amount']:,.2f}\n"
        
        specialized_context = self._build_specialized_context(dashboard_data, query_type)
        
        return f"""
You are an AI assistant for Renew-IQ, an insurance policy renewal management system. 
You help users analyze their renewal portfolio, optimize processes, and provide data-driven insights.

{user_info_text}

CURRENT SYSTEM DATA:
- Total Renewal Cases: {dashboard_data.get('renewal_cases', {}).get('total_cases', 0)}
- Renewed Cases: {dashboard_data.get('renewal_cases', {}).get('renewed', 0)}
- In Progress: {dashboard_data.get('renewal_cases', {}).get('in_progress', 0)}
- Pending Action: {dashboard_data.get('renewal_cases', {}).get('pending_action', 0)}
- Failed Cases: {dashboard_data.get('renewal_cases', {}).get('failed', 0)}
- Total Renewal Amount: ₹{dashboard_data.get('renewal_cases', {}).get('total_renewal_amount', 0):,.2f}

- Total Customers: {dashboard_data.get('customers', {}).get('total_customers', 0)}
- Active Customers: {dashboard_data.get('customers', {}).get('active_customers', 0)}
- Verified Customers: {dashboard_data.get('customers', {}).get('verified_customers', 0)}

- Total Payments: {dashboard_data.get('payments', {}).get('total_payments', 0)}
- Completed Payments: {dashboard_data.get('payments', {}).get('completed_payments', 0)}
- Total Collected: ₹{dashboard_data.get('payments', {}).get('total_collected', 0):,.2f}

- Total Campaigns: {dashboard_data.get('campaigns', {}).get('total_campaigns', 0)}
- Active Campaigns: {dashboard_data.get('campaigns', {}).get('active_campaigns', 0)}

- Total Policies: {dashboard_data.get('policies', {}).get('total_policies', 0)}
- Active Policies: {dashboard_data.get('policies', {}).get('active_policies', 0)}
- Recent Renewals (30 days): {dashboard_data.get('recent_renewals_count', 0)}

{policy_details_text}{expiring_text}

{specialized_context}

CRITICAL INSTRUCTIONS:
1. ALWAYS provide specific, data-driven insights based on the actual data provided above
2. Use exact numbers, percentages, and metrics from the database
3. Identify specific patterns, trends, and anomalies in the data
4. Provide actionable recommendations based on the actual data analysis
5. When discussing performance, use the specific metrics provided
6. For churn analysis, focus on the actual churn rates, failed renewals, and customer patterns
7. For renewal performance, analyze the specific success rates, channel performance, and timing patterns
8. For payment analysis, discuss the actual payment trends, methods, and outstanding amounts
9. Always explain the "why" behind the data - what factors contribute to the current situation
10. Provide specific, measurable action items that can improve the metrics
11. Use the specialized data sections to provide deep, contextual analysis
12. Never give generic advice - always tie recommendations to the specific data patterns observed

RESPONSE FORMAT:
- Start with key findings from the data
- Explain the significance of these findings
- Provide specific recommendations with expected impact
- Include actionable next steps
- Use data to support all claims and recommendations
"""
    
    def _build_specialized_context(self, dashboard_data: Dict[str, Any], query_type: str) -> str:
        """Build specialized context based on query type"""
        if query_type == 'customer_churn':
            return self._build_churn_context(dashboard_data.get('churn_analysis', {}))
        elif query_type == 'renewal_performance':
            return self._build_renewal_performance_context(dashboard_data.get('renewal_performance', {}))
        elif query_type == 'payment_analysis':
            return self._build_payment_analysis_context(dashboard_data.get('payment_analysis', {}))
        elif query_type == 'campaign_performance':
            return self._build_campaign_performance_context(dashboard_data.get('campaign_performance', {}))
        elif query_type == 'customer_insights':
            return self._build_customer_insights_context(dashboard_data.get('customer_insights', {}))
        elif query_type == 'process_optimization':
            return self._build_process_optimization_context(dashboard_data.get('process_optimization', {}))
        elif query_type == 'predictive_insights':
            return self._build_predictive_insights_context(dashboard_data.get('predictive_insights', {}))
        else:
            return ""

    def _build_churn_context(self, churn_data: Dict[str, Any]) -> str:
        """Build context for customer churn analysis"""
        if not churn_data:
            return ""
        
        context = "\n\nCUSTOMER CHURN ANALYSIS DATA:\n"
        context += f"- Total Renewals (30 days): {churn_data.get('total_renewals_30_days', 0)}\n"
        context += f"- Failed Renewals: {churn_data.get('failed_renewals', 0)}\n"
        context += f"- Cancelled Renewals: {churn_data.get('cancelled_renewals', 0)}\n"
        context += f"- Expired Renewals: {churn_data.get('expired_renewals', 0)}\n"
        context += f"- Total Churned: {churn_data.get('total_churned', 0)}\n"
        context += f"- Current Churn Rate: {churn_data.get('churn_rate', 0)}%\n"
        context += f"- Old Customers (90+ days inactive): {churn_data.get('old_customers_count', 0)}\n"
        context += f"- Policies Expiring (60 days): {churn_data.get('expiring_policies_60_days', 0)}\n"
        context += f"- Already Expired Policies: {churn_data.get('expired_policies', 0)}\n"
        
        payment_patterns = churn_data.get('payment_patterns', [])
        if payment_patterns:
            context += "\nPAYMENT PATTERNS (60 days):\n"
            for pattern in payment_patterns:
                context += f"- {pattern.get('payment_status', 'Unknown')}: {pattern.get('count', 0)} payments (₹{pattern.get('total_amount', 0):,.2f})\n"
        
        comm_attempts = churn_data.get('communication_attempts', [])
        if comm_attempts:
            context += "\nCOMMUNICATION ATTEMPTS (30 days):\n"
            for attempt in comm_attempts:
                context += f"- {attempt.get('channel_type', 'Unknown')}: {attempt.get('count', 0)} attempts, {attempt.get('success_count', 0)} successful\n"
        
        return context

    def _build_renewal_performance_context(self, renewal_data: Dict[str, Any]) -> str:
        """Build context for renewal performance analysis"""
        if not renewal_data:
            return ""
        
        context = "\n\nRENEWAL PERFORMANCE ANALYSIS DATA:\n"
        context += f"- Total Cases: {renewal_data.get('total_cases', 0)}\n"
        
        status_breakdown = renewal_data.get('status_breakdown', [])
        if status_breakdown:
            context += "\nSTATUS BREAKDOWN:\n"
            for status in status_breakdown:
                context += f"- {status.get('status', 'Unknown')}: {status.get('count', 0)} cases (₹{status.get('total_amount', 0):,.2f})\n"
        
      
        channel_performance = renewal_data.get('channel_performance', [])
        if channel_performance:
            context += "\nCHANNEL PERFORMANCE:\n"
            for channel in channel_performance:
                context += f"- {channel.get('channel_id__name', 'Unknown')}: {channel.get('successful_cases', 0)}/{channel.get('total_cases', 0)} success ({channel.get('success_rate', 0):.1f}%)\n"
        
        return context

    def _build_payment_analysis_context(self, payment_data: Dict[str, Any]) -> str:
        """Build context for payment analysis"""
        if not payment_data:
            return ""
        
        context = "\n\nPAYMENT ANALYSIS DATA:\n"
        
       
        status_breakdown = payment_data.get('status_breakdown', [])
        if status_breakdown:
            context += "\nPAYMENT STATUS BREAKDOWN:\n"
            for status in status_breakdown:
                context += f"- {status.get('payment_status', 'Unknown')}: {status.get('count', 0)} payments (₹{status.get('total_amount', 0):,.2f})\n"
        
      
        payment_methods = payment_data.get('payment_methods', [])
        if payment_methods:
            context += "\nPAYMENT METHODS (30 days):\n"
            for method in payment_methods:
                context += f"- {method.get('payment_method', 'Unknown')}: {method.get('count', 0)} payments, {method.get('success_rate', 0):.1f}% success\n"
        
        
        outstanding = payment_data.get('outstanding_amounts', {})
        if outstanding:
            context += f"\nOUTSTANDING AMOUNTS: ₹{outstanding.get('total_outstanding', 0):,.2f} ({outstanding.get('count', 0)} cases)\n"
        
        return context

    def _build_campaign_performance_context(self, campaign_data: Dict[str, Any]) -> str:
        """Build context for campaign performance analysis"""
        if not campaign_data:
            return ""
        
        context = "\n\nCAMPAIGN PERFORMANCE DATA:\n"
        
        
        campaign_status = campaign_data.get('campaign_status', [])
        if campaign_status:
            context += "\nCAMPAIGN STATUS:\n"
            for status in campaign_status:
                context += f"- {status.get('status', 'Unknown')}: {status.get('count', 0)} campaigns\n"
        
        
        active_campaigns = campaign_data.get('active_campaigns', [])
        if active_campaigns:
            context += "\nACTIVE CAMPAIGNS (30 days):\n"
            for campaign in active_campaigns:
                context += f"- {campaign.get('campaign_type__name', 'Unknown')}: {campaign.get('count', 0)} campaigns, {campaign.get('total_targets', 0)} targets\n"
        
      
        email_performance = campaign_data.get('email_performance', [])
        if email_performance:
            context += "\nEMAIL PERFORMANCE (30 days):\n"
            for email in email_performance:
                context += f"- {email.get('status', 'Unknown')}: {email.get('count', 0)} emails, {email.get('total_recipients', 0)} recipients\n"
        
       
        channel_effectiveness = campaign_data.get('channel_effectiveness', {})
        if channel_effectiveness:
            context += "\nCHANNEL EFFECTIVENESS ANALYSIS:\n"
            
            
            channel_renewal_performance = channel_effectiveness.get('channel_renewal_performance', [])
            if channel_renewal_performance:
                context += "\nRENEWAL SUCCESS BY CHANNEL (60 days):\n"
                for channel in channel_renewal_performance:
                    context += f"- {channel.get('channel_id__name', 'Unknown')} ({channel.get('channel_id__channel_type', 'Unknown')}): {channel.get('success_rate', 0):.1f}% success rate ({channel.get('successful_cases', 0)}/{channel.get('total_cases', 0)} cases)\n"
                    context += f"  Total Amount: ₹{channel.get('total_amount', 0):,.2f}\n"
            
            
            communication_channel_performance = channel_effectiveness.get('communication_channel_performance', [])
            if communication_channel_performance:
                context += "\nCOMMUNICATION SUCCESS BY CHANNEL (30 days):\n"
                for comm in communication_channel_performance:
                    context += f"- {comm.get('channel', 'Unknown')}: {comm.get('success_rate', 0):.1f}% success rate ({comm.get('successful_attempts', 0)}/{comm.get('total_attempts', 0)} attempts)\n"
                    context += f"  Failed: {comm.get('failed_attempts', 0)}, Bounced: {comm.get('bounced_attempts', 0)}\n"
            
        
            channels_info = channel_effectiveness.get('channels_info', [])
            if channels_info:
                context += "\nAVAILABLE CHANNELS:\n"
                for channel in channels_info:
                    context += f"- {channel.get('name', 'Unknown')} ({channel.get('channel_type', 'Unknown')}): Status: {channel.get('status', 'Unknown')}\n"
                    if channel.get('cost_per_lead'):
                        context += f"  Cost per Lead: ₹{channel.get('cost_per_lead', 0):,.2f}\n"
                    if channel.get('budget'):
                        context += f"  Budget: ₹{channel.get('budget', 0):,.2f}\n"
        
        
        communication_performance = campaign_data.get('communication_performance', {})
        if communication_performance:
            overall_stats = communication_performance.get('overall_stats', {})
            if overall_stats:
                context += f"\nOVERALL COMMUNICATION PERFORMANCE (30 days):\n"
                context += f"- Total Attempts: {overall_stats.get('total_attempts', 0)}\n"
                context += f"- Successful: {overall_stats.get('successful_attempts', 0)} ({overall_stats.get('success_rate', 0)}%)\n"
                context += f"- Failed: {overall_stats.get('failed_attempts', 0)}\n"
                context += f"- Bounced: {overall_stats.get('bounced_attempts', 0)}\n"
            
            channel_type_performance = communication_performance.get('channel_type_performance', [])
            if channel_type_performance:
                context += "\nPERFORMANCE BY CHANNEL TYPE:\n"
                for channel_type in channel_type_performance:
                    context += f"- {channel_type.get('channel', 'Unknown')}: {channel_type.get('success_rate', 0):.1f}% success ({channel_type.get('successful_attempts', 0)}/{channel_type.get('total_attempts', 0)})\n"
        
      
        campaign_recipient_performance = campaign_data.get('campaign_recipient_performance', {})
        if campaign_recipient_performance:
            email_perf = campaign_recipient_performance.get('email_performance', [])
            whatsapp_perf = campaign_recipient_performance.get('whatsapp_performance', [])
            sms_perf = campaign_recipient_performance.get('sms_performance', [])
            
            if email_perf:
                context += "\nEMAIL CAMPAIGN PERFORMANCE (30 days):\n"
                for perf in email_perf:
                    context += f"- Status: {perf.get('email_status', 'Unknown')}, Engagement: {perf.get('email_engagement', 'Unknown')}: {perf.get('count', 0)} recipients\n"
            
            if whatsapp_perf:
                context += "\nWHATSAPP CAMPAIGN PERFORMANCE (30 days):\n"
                for perf in whatsapp_perf:
                    context += f"- Status: {perf.get('whatsapp_status', 'Unknown')}, Engagement: {perf.get('whatsapp_engagement', 'Unknown')}: {perf.get('count', 0)} recipients\n"
            
            if sms_perf:
                context += "\nSMS CAMPAIGN PERFORMANCE (30 days):\n"
                for perf in sms_perf:
                    context += f"- Status: {perf.get('sms_status', 'Unknown')}, Engagement: {perf.get('sms_engagement', 'Unknown')}: {perf.get('count', 0)} recipients\n"
        
        return context

    def _build_customer_insights_context(self, customer_data: Dict[str, Any]) -> str:
        """Build context for customer insights"""
        if not customer_data:
            return ""
        
        context = "\n\nCUSTOMER INSIGHTS DATA:\n"
        
     
        demographics = customer_data.get('demographics', [])
        if demographics:
            context += "\nCUSTOMER DEMOGRAPHICS:\n"
            for demo in demographics:
                context += f"- {demo.get('gender', 'Unknown')}: {demo.get('count', 0)} customers\n"
        
        
        policy_dist = customer_data.get('policy_distribution', {})
        if policy_dist:
            context += f"\nPOLICY DISTRIBUTION:\n"
            context += f"- Average Policies per Customer: {policy_dist.get('avg_policies', 0):.1f}\n"
            context += f"- Average Active Policies: {policy_dist.get('avg_active_policies', 0):.1f}\n"
        
        return context

    def _build_process_optimization_context(self, process_data: Dict[str, Any]) -> str:
        """Build context for process optimization"""
        if not process_data:
            return ""
        
        context = "\n\nPROCESS OPTIMIZATION DATA:\n"
        
  
        processing_times = process_data.get('processing_times', [])
        if processing_times:
            context += "\nAVERAGE PROCESSING TIMES:\n"
            for time in processing_times:
                context += f"- {time.get('status', 'Unknown')}: {time.get('avg_processing_days', 0):.1f} days ({time.get('count', 0)} cases)\n"
        
    
        bottlenecks = process_data.get('bottleneck_analysis', [])
        if bottlenecks:
            context += "\nBOTTLENECK ANALYSIS:\n"
            for bottleneck in bottlenecks:
                context += f"- {bottleneck.get('status', 'Unknown')}: {bottleneck.get('count', 0)} cases\n"
        
        return context

    def _build_predictive_insights_context(self, predictive_data: Dict[str, Any]) -> str:
        """Build context for predictive insights"""
        if not predictive_data:
            return ""
        
        context = "\n\nPREDICTIVE INSIGHTS DATA:\n"
        
    
        expiring_policies = predictive_data.get('expiring_policies', [])
        if expiring_policies:
            context += "\nPOLICIES EXPIRING (90 days):\n"
            for policy in expiring_policies:
                context += f"- {policy.get('policy_type__name', 'Unknown')}: {policy.get('count', 0)} policies (₹{policy.get('total_premium', 0):,.2f})\n"
        
        
        renewal_likelihood = predictive_data.get('renewal_likelihood', [])
        if renewal_likelihood:
            context += "\nRENEWAL LIKELIHOOD (by policy type):\n"
            for likelihood in renewal_likelihood:
                context += f"- {likelihood.get('policy__policy_type__name', 'Unknown')}: {likelihood.get('renewal_rate', 0):.1f}% ({likelihood.get('renewed_cases', 0)}/{likelihood.get('total_cases', 0)})\n"
        
        return context
    
    def get_quick_suggestions(self) -> List[Dict[str, str]]:
        return [
            {
                "id": "analyze_portfolio",
                "title": "Analyze my current renewal portfolio performance",
                "description": "Get insights on renewal rates, success metrics, and performance trends"
            },
            {
                "id": "improve_renewal_rates",
                "title": "What strategies can improve my renewal rates?",
                "description": "Discover proven strategies to increase customer retention and renewal success"
            },
            {
                "id": "optimize_digital_channels",
                "title": "How can I optimize my digital channel performance?",
                "description": "Analyze email, SMS, and WhatsApp campaign effectiveness"
            },
            {
                "id": "identify_bottlenecks",
                "title": "What are the key bottlenecks in my renewal process?",
                "description": "Identify process inefficiencies and optimization opportunities"
            },
            {
                "id": "premium_collection_insights",
                "title": "Provide insights on my premium collection efficiency",
                "description": "Analyze payment patterns and collection strategies"
            },
            {
                "id": "reduce_customer_churn",
                "title": "How can I reduce customer churn this quarter?",
                "description": "Get actionable strategies to improve customer retention"
            },
            {
                "id": "predictive_insights",
                "title": "What predictive insights do you see in my data?",
                "description": "Discover trends and predictions based on your current data"
            }
        ]
    
    def analyze_renewal_performance(self) -> Dict[str, Any]:
        try:
            dashboard_data = self.get_dashboard_data()
            renewal_data = dashboard_data.get('renewal_cases', {})
            
            total_cases = renewal_data.get('total_cases', 0)
            renewed = renewal_data.get('renewed', 0)
            in_progress = renewal_data.get('in_progress', 0)
            pending = renewal_data.get('pending_action', 0)
            failed = renewal_data.get('failed', 0)
            
            renewal_rate = (renewed / total_cases * 100) if total_cases > 0 else 0
            success_rate = ((renewed + in_progress) / total_cases * 100) if total_cases > 0 else 0
            failure_rate = (failed / total_cases * 100) if total_cases > 0 else 0
            
            insights = []
            if renewal_rate < 70:
                insights.append("Renewal rate is below industry average (70%). Focus on customer engagement.")
            if failure_rate > 20:
                insights.append("High failure rate detected. Review process bottlenecks.")
            if pending > total_cases * 0.3:
                insights.append("High pending cases. Consider automation for routine tasks.")
            
            return {
                'success': True,
                'metrics': {
                    'renewal_rate': round(renewal_rate, 2),
                    'success_rate': round(success_rate, 2),
                    'failure_rate': round(failure_rate, 2),
                    'total_cases': total_cases,
                    'renewed': renewed,
                    'in_progress': in_progress,
                    'pending': pending,
                    'failed': failed
                },
                'insights': insights,
                'recommendations': self._get_renewal_recommendations(renewal_rate, failure_rate)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing renewal performance: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_renewal_recommendations(self, renewal_rate: float, failure_rate: float) -> List[str]:
        recommendations = []
        
        if renewal_rate < 60:
            recommendations.extend([
                "Implement automated renewal reminders 60 days before expiry",
                "Create personalized renewal offers based on customer history",
                "Set up multi-channel communication (email, SMS, WhatsApp)"
            ])
        elif renewal_rate < 80:
            recommendations.extend([
                "Focus on high-value customers with personalized outreach",
                "Implement customer feedback surveys to identify pain points",
                "Optimize renewal process for faster completion"
            ])
        
        if failure_rate > 15:
            recommendations.extend([
                "Review and simplify renewal documentation requirements",
                "Implement payment plan options for customers",
                "Provide 24/7 customer support during renewal period"
            ])
        
        return recommendations

    def _classify_query(self, user_message: str) -> str:
        """Classify the type of query to determine what data to fetch"""
        message_lower = user_message.lower()
        
        if any(keyword in message_lower for keyword in ['churn', 'retention', 'losing customers', 'customer loss', 'reduce churn']):
            return 'customer_churn'
        
        elif any(keyword in message_lower for keyword in ['renewal rate', 'renewal performance', 'renewal success', 'renewal analysis']):
            return 'renewal_performance'
        
        elif any(keyword in message_lower for keyword in ['payment', 'premium collection', 'payment efficiency', 'payment pattern']):
            return 'payment_analysis'
        
        elif any(keyword in message_lower for keyword in ['campaign', 'email', 'whatsapp', 'sms', 'communication', 'digital channel']):
            return 'campaign_performance'
        
        elif any(keyword in message_lower for keyword in ['customer insights', 'customer behavior', 'customer profile', 'customer analysis']):
            return 'customer_insights'
        
        elif any(keyword in message_lower for keyword in ['bottleneck', 'process', 'efficiency', 'optimization', 'improve process']):
            return 'process_optimization'
        
        elif any(keyword in message_lower for keyword in ['predict', 'forecast', 'trend', 'future', 'predictive']):
            return 'predictive_insights'
        
        elif any(keyword in message_lower for keyword in ['portfolio', 'overall performance', 'dashboard', 'summary']):
            return 'portfolio_analysis'
        
        else:
            return 'general'

    def _get_specialized_data(self, query_type: str, user_message: str) -> Dict[str, Any]:
        """Fetch specialized data based on query type"""
        try:
            if query_type == 'customer_churn':
                return self._get_churn_analysis_data()
            elif query_type == 'renewal_performance':
                return self._get_renewal_performance_data()
            elif query_type == 'payment_analysis':
                return self._get_payment_analysis_data()
            elif query_type == 'campaign_performance':
                return self._get_campaign_performance_data()
            elif query_type == 'customer_insights':
                return self._get_customer_insights_data()
            elif query_type == 'process_optimization':
                return self._get_process_optimization_data()
            elif query_type == 'predictive_insights':
                return self._get_predictive_insights_data()
            else:
                return {}
        except Exception as e:
            logger.error(f"Error fetching specialized data for {query_type}: {str(e)}")
            return {}

    def _get_churn_analysis_data(self) -> Dict[str, Any]:
        """Get comprehensive data for customer churn analysis"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            sixty_days_ago = today - timedelta(days=60)
            ninety_days_ago = today - timedelta(days=90)
            
            recent_renewals = RenewalCase.objects.filter(
                is_deleted=False,
                created_at__gte=thirty_days_ago
            )
            
            total_renewals = recent_renewals.count()
            failed_renewals = recent_renewals.filter(status='failed').count()
            cancelled_renewals = recent_renewals.filter(status='cancelled').count()
            expired_renewals = recent_renewals.filter(status='expired').count()
            
            total_churned = failed_renewals + cancelled_renewals + expired_renewals
            churn_rate = (total_churned / total_renewals * 100) if total_renewals > 0 else 0
            
            old_customers = Customer.objects.filter(
                is_deleted=False,
                status='active',
                updated_at__lte=ninety_days_ago
            )
            
            payment_patterns = CustomerPayment.objects.filter(
                is_deleted=False,
                created_at__gte=sixty_days_ago
            ).values('payment_status').annotate(
                count=Count('id'),
                total_amount=Sum('payment_amount')
            )
            
            from apps.customer_communication_preferences.models import CommunicationLog
            communication_attempts = CommunicationLog.objects.filter(
                created_at__gte=thirty_days_ago
            ).values('channel_type').annotate(
                count=Count('id'),
                success_count=Count('id', filter=Q(status='success'))
            )
            
            expiring_policies = Policy.objects.filter(
                is_deleted=False,
                end_date__gte=today,
                end_date__lte=today + timedelta(days=60)
            ).count()
            
            expired_policies = Policy.objects.filter(
                is_deleted=False,
                end_date__lt=today,
                status='active'
            ).count()
            
            return {
                'churn_analysis': {
                    'total_renewals_30_days': total_renewals,
                    'failed_renewals': failed_renewals,
                    'cancelled_renewals': cancelled_renewals,
                    'expired_renewals': expired_renewals,
                    'total_churned': total_churned,
                    'churn_rate': round(churn_rate, 2),
                    'old_customers_count': old_customers.count(),
                    'payment_patterns': list(payment_patterns),
                    'communication_attempts': list(communication_attempts),
                    'expiring_policies_60_days': expiring_policies,
                    'expired_policies': expired_policies,
                }
            }
            
        except Exception as e:
            logger.error(f"Error in churn analysis data: {str(e)}")
            return {'churn_analysis': {}}

    def _get_renewal_performance_data(self) -> Dict[str, Any]:
        """Get comprehensive data for renewal performance analysis"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            sixty_days_ago = today - timedelta(days=60)
            
            renewal_cases = RenewalCase.objects.filter(is_deleted=False)
            
            status_breakdown = renewal_cases.values('status').annotate(
                count=Count('id'),
                total_amount=Sum('renewal_amount')
            )
            
            recent_performance = renewal_cases.filter(
                created_at__gte=thirty_days_ago
            ).values('status').annotate(
                count=Count('id'),
                avg_amount=Avg('renewal_amount')
            )
            
            channel_performance = renewal_cases.filter(
                channel_id__isnull=False
            ).values('channel_id__name').annotate(
                total_cases=Count('id'),
                successful_cases=Count('id', filter=Q(status='renewed')),
                success_rate=Count('id', filter=Q(status='renewed')) * 100.0 / Count('id')
            )
            
            timing_analysis = renewal_cases.filter(
                created_at__gte=sixty_days_ago
            ).extra(
                select={'day_of_week': 'EXTRACT(dow FROM created_at)'}
            ).values('day_of_week').annotate(
                count=Count('id'),
                success_count=Count('id', filter=Q(status='renewed'))
            )
            
            return {
                'renewal_performance': {
                    'status_breakdown': list(status_breakdown),
                    'recent_performance': list(recent_performance),
                    'channel_performance': list(channel_performance),
                    'timing_analysis': list(timing_analysis),
                    'total_cases': renewal_cases.count(),
                }
            }
            
        except Exception as e:
            logger.error(f"Error in renewal performance data: {str(e)}")
            return {'renewal_performance': {}}

    def _get_payment_analysis_data(self) -> Dict[str, Any]:
        """Get comprehensive data for payment analysis"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            ninety_days_ago = today - timedelta(days=90)
            
            payments = CustomerPayment.objects.filter(is_deleted=False)
            
            payment_status_breakdown = payments.values('payment_status').annotate(
                count=Count('id'),
                total_amount=Sum('payment_amount'),
                avg_amount=Avg('payment_amount')
            )
            
            payment_trends = payments.filter(
                created_at__gte=ninety_days_ago
            ).extra(
                select={'month': 'EXTRACT(month FROM created_at)'}
            ).values('month').annotate(
                count=Count('id'),
                total_amount=Sum('payment_amount'),
                success_count=Count('id', filter=Q(payment_status='completed'))
            )
            
            payment_methods = payments.filter(
                created_at__gte=thirty_days_ago
            ).values('payment_method').annotate(
                count=Count('id'),
                total_amount=Sum('payment_amount'),
                success_rate=Count('id', filter=Q(payment_status='completed')) * 100.0 / Count('id')
            )
            
            outstanding_amounts = RenewalCase.objects.filter(
                is_deleted=False,
                payment_status='pending'
            ).aggregate(
                total_outstanding=Sum('renewal_amount'),
                count=Count('id')
            )
            
            return {
                'payment_analysis': {
                    'status_breakdown': list(payment_status_breakdown),
                    'payment_trends': list(payment_trends),
                    'payment_methods': list(payment_methods),
                    'outstanding_amounts': outstanding_amounts,
                }
            }
            
        except Exception as e:
            logger.error(f"Error in payment analysis data: {str(e)}")
            return {'payment_analysis': {}}

    def _get_campaign_performance_data(self) -> Dict[str, Any]:
        """Get comprehensive data for campaign performance analysis"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)
            sixty_days_ago = today - timedelta(days=60)
            
            campaigns = Campaign.objects.filter(is_deleted=False)
            
            campaign_status = campaigns.values('status').annotate(
                count=Count('id')
            )
            
            active_campaigns = campaigns.filter(
                status='active',
                created_at__gte=thirty_days_ago
            ).values('campaign_type__name').annotate(
                count=Count('id'),
                total_targets=Sum('target_count')
            )
            
            try:
                from apps.email_operations.models import EmailOperation
                email_performance = EmailOperation.objects.filter(
                    created_at__gte=thirty_days_ago
                ).values('status').annotate(
                    count=Count('id'),
                    total_recipients=Sum('recipient_count')
                )
            except:
                email_performance = []
            
            channel_effectiveness = self._get_channel_effectiveness_data(thirty_days_ago, sixty_days_ago)
            
            communication_performance = self._get_communication_performance_data(thirty_days_ago)
            
            campaign_recipient_performance = self._get_campaign_recipient_performance(thirty_days_ago)
            
            return {
                'campaign_performance': {
                    'campaign_status': list(campaign_status),
                    'active_campaigns': list(active_campaigns),
                    'email_performance': list(email_performance),
                    'channel_effectiveness': channel_effectiveness,
                    'communication_performance': communication_performance,
                    'campaign_recipient_performance': campaign_recipient_performance,
                }
            }
            
        except Exception as e:
            logger.error(f"Error in campaign performance data: {str(e)}")
            return {'campaign_performance': {}}

    def _get_channel_effectiveness_data(self, thirty_days_ago, sixty_days_ago):
        """Get comprehensive channel effectiveness data"""
        try:
            from apps.channels.models import Channel
            channel_renewal_performance = RenewalCase.objects.filter(
                is_deleted=False,
                channel_id__isnull=False,
                created_at__gte=sixty_days_ago
            ).values('channel_id__name', 'channel_id__channel_type').annotate(
                total_cases=Count('id'),
                successful_cases=Count('id', filter=Q(status='renewed')),
                failed_cases=Count('id', filter=Q(status='failed')),
                success_rate=Count('id', filter=Q(status='renewed')) * 100.0 / Count('id'),
                total_amount=Sum('renewal_amount')
            ).order_by('-success_rate')
            
            channels_info = Channel.objects.filter(
                is_deleted=False
            ).values('id', 'name', 'channel_type', 'status', 'cost_per_lead', 'budget')
            
            from apps.customer_communication_preferences.models import CommunicationLog
            communication_channel_performance = CommunicationLog.objects.filter(
                communication_date__gte=thirty_days_ago
            ).values('channel').annotate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])),
                success_rate=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])) * 100.0 / Count('id'),
                failed_attempts=Count('id', filter=Q(outcome='failed')),
                bounced_attempts=Count('id', filter=Q(outcome='bounced'))
            ).order_by('-success_rate')
            
            return {
                'channel_renewal_performance': list(channel_renewal_performance),
                'channels_info': list(channels_info),
                'communication_channel_performance': list(communication_channel_performance)
            }
            
        except Exception as e:
            logger.error(f"Error in channel effectiveness data: {str(e)}")
            return {}

    def _get_communication_performance_data(self, thirty_days_ago):
        """Get communication performance data"""
        try:
            from apps.customer_communication_preferences.models import CommunicationLog
            
            communication_stats = CommunicationLog.objects.filter(
                communication_date__gte=thirty_days_ago
            ).aggregate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])),
                failed_attempts=Count('id', filter=Q(outcome='failed')),
                bounced_attempts=Count('id', filter=Q(outcome='bounced'))
            )
            
            total_attempts = communication_stats.get('total_attempts', 0)
            successful_attempts = communication_stats.get('successful_attempts', 0)
            success_rate = (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0
            
            channel_type_performance = CommunicationLog.objects.filter(
                communication_date__gte=thirty_days_ago
            ).values('channel').annotate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])),
                success_rate=Count('id', filter=Q(outcome__in=['successful', 'delivered', 'opened', 'clicked', 'replied'])) * 100.0 / Count('id')
            ).order_by('-success_rate')
            
            return {
                'overall_stats': {
                    'total_attempts': total_attempts,
                    'successful_attempts': successful_attempts,
                    'failed_attempts': communication_stats.get('failed_attempts', 0),
                    'bounced_attempts': communication_stats.get('bounced_attempts', 0),
                    'success_rate': round(success_rate, 2)
                },
                'channel_type_performance': list(channel_type_performance)
            }
            
        except Exception as e:
            logger.error(f"Error in communication performance data: {str(e)}")
            return {}

    def _get_campaign_recipient_performance(self, thirty_days_ago):
        """Get campaign recipient performance by channel"""
        try:
            from apps.campaigns.models import CampaignRecipient
            
            email_performance = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('email_status', 'email_engagement').annotate(
                count=Count('id')
            )
            
            whatsapp_performance = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('whatsapp_status', 'whatsapp_engagement').annotate(
                count=Count('id')
            )
            
            sms_performance = CampaignRecipient.objects.filter(
                campaign__created_at__gte=thirty_days_ago
            ).values('sms_status', 'sms_engagement').annotate(
                count=Count('id')
            )
            
            return {
                'email_performance': list(email_performance),
                'whatsapp_performance': list(whatsapp_performance),
                'sms_performance': list(sms_performance)
            }
            
        except Exception as e:
            logger.error(f"Error in campaign recipient performance: {str(e)}")
            return {}

    def _get_customer_insights_data(self) -> Dict[str, Any]:
        """Get comprehensive data for customer insights"""
        try:
            customers = Customer.objects.filter(is_deleted=False)
            
            customer_demographics = customers.values('gender').annotate(
                count=Count('id')
            )
            
            customer_policies = customers.annotate(
                policy_count=Count('policies'),
                active_policy_count=Count('policies', filter=Q(policies__status='active'))
            ).aggregate(
                avg_policies=Avg('policy_count'),
                avg_active_policies=Avg('active_policy_count')
            )
            
            from apps.customer_communication_preferences.models import CustomerCommunicationPreference
            comm_preferences = CustomerCommunicationPreference.objects.filter(
                is_deleted=False
            ).values('preferred_channel').annotate(
                count=Count('id')
            )
            
            payment_behavior = CustomerPayment.objects.filter(
                is_deleted=False
            ).values('customer__id').annotate(
                total_payments=Count('id'),
                total_amount=Sum('payment_amount'),
                success_rate=Count('id', filter=Q(payment_status='completed')) * 100.0 / Count('id')
            ).order_by('-total_amount')[:10]
            
            return {
                'customer_insights': {
                    'demographics': list(customer_demographics),
                    'policy_distribution': customer_policies,
                    'communication_preferences': list(comm_preferences),
                    'top_customers_by_payment': list(payment_behavior),
                }
            }
            
        except Exception as e:
            logger.error(f"Error in customer insights data: {str(e)}")
            return {'customer_insights': {}}

    def _get_process_optimization_data(self) -> Dict[str, Any]:
        """Get comprehensive data for process optimization"""
        try:
            renewal_cases = RenewalCase.objects.filter(is_deleted=False)
            
            processing_times = renewal_cases.extra(
                select={'processing_days': 'EXTRACT(days FROM updated_at - created_at)'}
            ).values('status').annotate(
                avg_processing_days=Avg('processing_days'),
                count=Count('id')
            )
            
            bottleneck_analysis = renewal_cases.filter(
                status__in=['pending', 'in_progress']
            ).values('status').annotate(
                count=Count('id'),
                avg_age=Avg('updated_at')
            )
            
            assignment_efficiency = renewal_cases.filter(
                assigned_to__isnull=False
            ).values('assigned_to__username').annotate(
                total_cases=Count('id'),
                completed_cases=Count('id', filter=Q(status='renewed')),
                completion_rate=Count('id', filter=Q(status='renewed')) * 100.0 / Count('id')
            )
            
            return {
                'process_optimization': {
                    'processing_times': list(processing_times),
                    'bottleneck_analysis': list(bottleneck_analysis),
                    'assignment_efficiency': list(assignment_efficiency),
                }
            }
            
        except Exception as e:
            logger.error(f"Error in process optimization data: {str(e)}")
            return {'process_optimization': {}}

    def _get_predictive_insights_data(self) -> Dict[str, Any]:
        """Get comprehensive data for predictive insights"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            
            expiring_policies = Policy.objects.filter(
                is_deleted=False,
                end_date__gte=today,
                end_date__lte=today + timedelta(days=90)
            ).values('policy_type__name').annotate(
                count=Count('id'),
                total_premium=Sum('premium_amount')
            )
            
            historical_renewals = RenewalCase.objects.filter(
                is_deleted=False,
                created_at__gte=today - timedelta(days=365)
            ).values('policy__policy_type__name').annotate(
                total_cases=Count('id'),
                renewed_cases=Count('id', filter=Q(status='renewed')),
                renewal_rate=Count('id', filter=Q(status='renewed')) * 100.0 / Count('id')
            )
            
            seasonal_trends = RenewalCase.objects.filter(
                is_deleted=False,
                created_at__gte=today - timedelta(days=365)
            ).extra(
                select={'month': 'EXTRACT(month FROM created_at)'}
            ).values('month').annotate(
                count=Count('id'),
                success_rate=Count('id', filter=Q(status='renewed')) * 100.0 / Count('id')
            )
            
            return {
                'predictive_insights': {
                    'expiring_policies': list(expiring_policies),
                    'renewal_likelihood': list(historical_renewals),
                    'seasonal_trends': list(seasonal_trends),
                }
            }
            
        except Exception as e:
            logger.error(f"Error in predictive insights data: {str(e)}")
            return {'predictive_insights': {}}


_ai_service_instance = None

def get_ai_service():
    """Get or create the AI service instance"""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance

class LazyAIService:
    def __init__(self):
        self._service = None
    
    def __getattr__(self, name):
        if self._service is None:
            self._service = get_ai_service()
        return getattr(self._service, name)

ai_service = LazyAIService()
