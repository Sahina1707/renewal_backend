"""
AI Service Layer for OpenAI integration and dashboard analytics.
Handles AI conversations, insights generation, and data analysis.
"""

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

# Import existing models
from apps.renewals.models import RenewalCase
from apps.customer_payments.models import CustomerPayment
from apps.campaigns.models import Campaign
from apps.customers.models import Customer
from apps.policies.models import Policy

User = get_user_model()
logger = logging.getLogger(__name__)


class AIService:
    """Main AI service for handling OpenAI integration and analytics"""
    
    def __init__(self):
        self.openai_client = None
        self._initialize_openai()
    
    def _initialize_openai(self):
        """Initialize OpenAI client with API key"""
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
        """Check if AI service is available"""
        return (
            OPENAI_AVAILABLE and 
            self.openai_client is not None and 
            bool(getattr(settings, 'OPENAI_API_KEY', ''))
        )
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data for AI analysis"""
        try:
            # Get renewal cases data
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
            
            # Get payment data
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
            
            # Get campaign data
            campaigns = Campaign.objects.filter(is_deleted=False)
            campaign_stats = {
                'total_campaigns': campaigns.count(),
                'active_campaigns': campaigns.filter(status='active').count(),
                'completed_campaigns': campaigns.filter(status='completed').count(),
                'scheduled_campaigns': campaigns.filter(status='scheduled').count(),
            }
            
            # Get customer data
            customers = Customer.objects.filter(is_deleted=False)
            customer_stats = {
                'total_customers': customers.count(),
                'active_customers': customers.filter(is_active=True).count(),
                'verified_customers': customers.filter(
                    Q(email_verified=True) | Q(phone_verified=True) | Q(pan_verified=True)
                ).count(),
            }
            
            # Get policy data
            policies = Policy.objects.filter(is_deleted=False)
            policy_stats = {
                'total_policies': policies.count(),
                'active_policies': policies.filter(status='active').count(),
                'expired_policies': policies.filter(status='expired').count(),
                'renewed_policies': policies.filter(status='renewed').count(),
            }
            
            return {
                'renewal_cases': renewal_stats,
                'payments': payment_stats,
                'campaigns': campaign_stats,
                'customers': customer_stats,
                'policies': policy_stats,
                'timestamp': timezone.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error fetching dashboard data: {str(e)}")
            return {}
    
    def generate_ai_response(self, user_message: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate AI response using OpenAI API"""
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not available',
                'message': 'OpenAI API key not configured or service unavailable'
            }
        
        try:
         
            dashboard_data = self.get_dashboard_data()
            
            system_prompt = self._create_system_prompt(dashboard_data)
            
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
                'usage': response.usage,
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
    
    def _create_system_prompt(self, dashboard_data: Dict[str, Any]) -> str:
        """Create system prompt with current dashboard context"""
        return f"""
You are an AI assistant for Renew-IQ, an insurance policy renewal management system. 
You help users analyze their renewal portfolio, optimize processes, and provide insights.

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

Guidelines:
1. Provide actionable insights based on the data
2. Focus on renewal management, customer retention, and process optimization
3. Suggest specific strategies and improvements
4. Use Indian insurance industry context
5. Be concise but comprehensive
6. If asked about specific metrics, calculate and explain them
7. Always provide practical next steps
"""
    
    def get_quick_suggestions(self) -> List[Dict[str, str]]:
        """Get predefined quick suggestions for the AI assistant"""
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
        """Analyze renewal performance and provide insights"""
        try:
            dashboard_data = self.get_dashboard_data()
            renewal_data = dashboard_data.get('renewal_cases', {})
            
            total_cases = renewal_data.get('total_cases', 0)
            renewed = renewal_data.get('renewed', 0)
            in_progress = renewal_data.get('in_progress', 0)
            pending = renewal_data.get('pending_action', 0)
            failed = renewal_data.get('failed', 0)
            
            # Calculate metrics
            renewal_rate = (renewed / total_cases * 100) if total_cases > 0 else 0
            success_rate = ((renewed + in_progress) / total_cases * 100) if total_cases > 0 else 0
            failure_rate = (failed / total_cases * 100) if total_cases > 0 else 0
            
            # Generate insights
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
        """Get specific recommendations based on performance metrics"""
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


# Global AI service instance
ai_service = AIService()
