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
    
    def generate_ai_response(self, user_message: str, context_data: Dict[str, Any] = None, user=None) -> Dict[str, Any]:
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not available',
                'message': 'OpenAI API key not configured or service unavailable'
            }
        
        try:
         
            dashboard_data = self.get_dashboard_data()
            
            # Add user-specific data if user is provided
            if user:
                user_specific_data = self._get_user_specific_data(user)
                dashboard_data['user_specific'] = user_specific_data
            
            system_prompt = self._create_system_prompt(dashboard_data, user)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
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
            
            # Try to find customer by email (most common case)
            customer = None
            try:
                customer = Customer.objects.filter(
                    email=user.email,
                    status='active'
                ).first()
                logger.info(f"Customer lookup by email '{user.email}': {'Found' if customer else 'Not found'}")
            except Exception as e:
                logger.error(f"Error in customer lookup by email: {str(e)}")
            
            # If no customer found by email, try to find by name
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
            
            # If still no customer found, try partial name matching
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
                # Get user's policies
                user_policies = Policy.objects.filter(
                    customer=customer,
                    is_deleted=False
                ).select_related('policy_type').order_by('-end_date')
                
                # Get user's renewal cases
                user_renewal_cases = RenewalCase.objects.filter(
                    customer=customer,
                    is_deleted=False
                ).select_related('policy').order_by('-created_at')
                
                # Format policy data with benefits, coverages, and features
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
                    
                    # Get policy benefits, coverages, and features
                    if policy.policy_type:
                        # Get policy coverages
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
                        
                        # Get policy features
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
                        
                        # Get additional benefits (if any exist for this policy)
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
                
                # Format renewal cases
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
    
    def _create_system_prompt(self, dashboard_data: Dict[str, Any], user=None) -> str:
        
        detailed_policies = dashboard_data.get('detailed_policies', [])
        expiring_policies = dashboard_data.get('expiring_soon', [])
        user_specific = dashboard_data.get('user_specific', {})
        
        # User-specific information
        user_info_text = ""
        if user and user_specific:
            if user_specific.get('customer_found'):
                user_info_text = f"\n\nCURRENT USER INFORMATION:\n"
                user_info_text += f"Customer Name: {user_specific.get('customer_name')}\n"
                user_info_text += f"Email: {user_specific.get('customer_email')}\n"
                user_info_text += f"Phone: {user_specific.get('customer_phone')}\n"
                user_info_text += f"Total Policies: {user_specific.get('total_policies', 0)}\n"
                user_info_text += f"Active Policies: {user_specific.get('active_policies', 0)}\n\n"
                
                # User's policies
                user_policies = user_specific.get('policies', [])
                if user_policies:
                    user_info_text += "YOUR POLICIES:\n"
                    for policy in user_policies:
                        user_info_text += f"- Policy: {policy['policy_number']} | Type: {policy['policy_type']}\n"
                        user_info_text += f"  Start: {policy['start_date']} | End: {policy['end_date']} | Renewal: {policy['renewal_date'] or 'Not set'}\n"
                        user_info_text += f"  Premium: ₹{policy['premium_amount']:,.2f} | Sum Assured: ₹{policy['sum_assured']:,.2f} | Status: {policy['status']}\n"
                        
                        # Add coverages
                        coverages = policy.get('coverages', [])
                        if coverages:
                            user_info_text += f"  COVERAGES:\n"
                            for coverage in coverages:
                                user_info_text += f"    • {coverage['name']}: {coverage['description']}\n"
                                if coverage['amount'] > 0:
                                    user_info_text += f"      Coverage Amount: ₹{coverage['amount']:,.2f}\n"
                                if coverage['is_optional']:
                                    user_info_text += f"      Optional (Premium Impact: ₹{coverage['premium_impact']:,.2f})\n"
                        
                        # Add features
                        features = policy.get('features', [])
                        if features:
                            user_info_text += f"  FEATURES:\n"
                            for feature in features:
                                user_info_text += f"    • {feature['name']}: {feature['description']}\n"
                                if feature['value']:
                                    user_info_text += f"      Value: {feature['value']}\n"
                        
                        # Add additional benefits
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
                
                # User's renewal cases
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
        
        return f"""
You are an AI assistant for Renew-IQ, an insurance policy renewal management system. 
You help users analyze their renewal portfolio, optimize processes, and provide insights.

{user_info_text}

Current Dashboard Data:
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

CRITICAL GUIDELINES FOR USER-SPECIFIC QUERIES:
1. When asked about "my renewal date" or "when is my renewal", ALWAYS use the user-specific policy information provided above
2. When asked about "benefits", "coverages", "features", or "what are all the benefits for my policy", provide the specific benefits, coverages, and features from the user's policy data above
3. If the user has policies, provide their specific renewal dates, policy numbers, premium amounts, and ALL benefits/coverages/features
4. If the user has no policies but customer record exists, say: "I found your customer record, but you don't have any active policies yet. Please contact your insurance agent to create your first policy."
5. If no customer record exists for the user, say: "I couldn't find your customer record in our system. Please contact your insurance agent to set up your customer profile and policies."
6. Always address the user by their name when providing personal information
7. Use the exact policy numbers, dates, amounts, and benefit details from the user's specific data
8. If the user has multiple policies, list all of them with their respective renewal dates and benefits
9. For benefit queries, provide comprehensive details including coverage amounts, optional benefits, and premium impacts
10. If no benefits data is found for a policy, say: "We are currently working on updating the benefits information for your policy. Please contact your insurance agent for the most current benefits details."
11. Be personal and specific - this is their actual data, not generic information
12. Always provide actionable next steps based on their specific situation
"""
    
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


# Global AI service instance - lazy initialization
_ai_service_instance = None

def get_ai_service():
    """Get or create the AI service instance"""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance

# For backward compatibility - lazy initialization
class LazyAIService:
    def __init__(self):
        self._service = None
    
    def __getattr__(self, name):
        if self._service is None:
            self._service = get_ai_service()
        return getattr(self._service, name)

ai_service = LazyAIService()
