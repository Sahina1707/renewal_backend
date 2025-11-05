"""
Customer Insights services for data aggregation and calculations.
Simplified design with single insights model and JSON storage.
"""

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional
import json
from django.utils.timesince import timesince
from django.contrib.auth import get_user_model

from apps.customers.models import Customer
from apps.customer_payments.models import CustomerPayment
from apps.customer_payment_schedule.models import PaymentSchedule
from apps.customer_communication_preferences.models import CommunicationLog
from apps.policies.models import Policy, PolicyClaim
from apps.renewals.models import RenewalCase
from apps.case_logs.models import CaseLog
from .models import CustomerInsight

# --- IMPORT THE NEW TIMELINE MODEL ---
# This assumes it's in apps.policies.models
try:
    from apps.policies.models import ClaimTimelineEvent
except ImportError:
    print("WARNING: ClaimTimelineEvent model not found. Claims timeline will be empty.")
    ClaimTimelineEvent = None


User = get_user_model()


# New Global Constants/Definitions
COMMUNICATION_TOPICS = {
    'policy_inquiries': ['policy inquiry', 'coverage question', 'policy details'],
    'billing_questions': ['billing', 'payment error', 'premium calculation'],
    'complaints': ['complaint', 'delay', 'service issue'],
    'coverage_updates': ['coverage update', 'change of address', 'nominee update'],
}


class CustomerInsightsService:
    """Service class for calculating and managing customer insights"""
    
    def __init__(self):
        self.now = timezone.now()
        self.today = self.now.date()
    
    def _serialize_datetime(self, obj):
        """Convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._serialize_datetime(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(item) for item in obj]
        else:
            return obj
    

    def get_customer_insights(self, customer_id: int, force_recalculate: bool = False) -> Dict[str, Any]:
        """Get comprehensive customer insights with caching"""
        try:
            customer = Customer.objects.get(id=customer_id, is_deleted=False)
        except Customer.DoesNotExist:
            return {"error": "Customer not found"}
        
        # Check if we have cached insights
        insight_record, created = CustomerInsight.objects.get_or_create(
            customer=customer,
            defaults={'is_cached': False}
        )
        
        # Check if cached payment_reliability is "Unknown" but there are payments
        # This handles cases where old cached data needs to be updated with new calculation logic
        needs_recalculation_for_reliability = False
        if insight_record.is_cached and insight_record.payment_insights:
            payment_insights = insight_record.payment_insights
            payment_reliability = payment_insights.get('payment_reliability', '')
            total_payments = payment_insights.get('total_payments_made', 0)
            # If payment_reliability is "Unknown" but there are payments, recalculate
            if payment_reliability == "Unknown" and total_payments > 0:
                needs_recalculation_for_reliability = True
        
        # Recalculate if forced, expired, not cached, or needs recalculation for payment_reliability
        if force_recalculate or not insight_record.is_cached or insight_record.is_expired or needs_recalculation_for_reliability:
            insights_data = self._calculate_all_insights(customer)
            
            # Serialize datetime objects before storing in JSONFields
            insights_data['payment_insights'] = self._serialize_datetime(insights_data['payment_insights'])
            insights_data['communication_insights'] = self._serialize_datetime(insights_data['communication_insights'])
            insights_data['claims_insights'] = self._serialize_datetime(insights_data['claims_insights'])
            insights_data['profile_insights'] = self._serialize_datetime(insights_data['profile_insights'])
            
            # Update the insight record
            insight_record.payment_insights = insights_data['payment_insights']
            insight_record.communication_insights = insights_data['communication_insights']
            insight_record.claims_insights = insights_data['claims_insights']
            insight_record.profile_insights = insights_data['profile_insights']
            insight_record.is_cached = True
            insight_record.cache_expires_at = timezone.now() + timedelta(hours=24)
            insight_record.calculated_at = timezone.now() # Update calculated_at when recalculating
            insight_record.save()
        else:
            # Use cached data
            insights_data = {
                'payment_insights': insight_record.payment_insights,
                'communication_insights': insight_record.communication_insights,
                'claims_insights': insight_record.claims_insights,
                'profile_insights': insight_record.profile_insights,
            }
        
        # Always get fresh payment schedule and history (these change frequently)
        return {
            "customer_info": self._get_customer_basic_info(customer),
            "payment_insights": insights_data['payment_insights'],
            "communication_insights": insights_data['communication_insights'],
            "claims_insights": insights_data['claims_insights'],
            "profile_insights": insights_data['profile_insights'],
            "payment_schedule": self.get_payment_schedule(customer),
            "payment_history": self.get_payment_history(customer),
            "calculated_at": insight_record.calculated_at,
            "is_cached": insight_record.is_cached,
        }
    
    def _calculate_all_insights(self, customer: Customer) -> Dict[str, Any]:
        """Calculate all insights for a customer"""
        return {
            "payment_insights": self.calculate_payment_insights(customer),
            "communication_insights": self.calculate_communication_insights(customer),
            "claims_insights": self.calculate_claims_insights(customer),
            "profile_insights": self.calculate_profile_insights(customer),
        }
    
    def _get_customer_basic_info(self, customer: Customer) -> Dict[str, Any]:
        """Get basic customer information"""
        # Manually combine first/last name
        full_name = f"{customer.first_name} {customer.last_name}".strip()

        return {
            "id": customer.id,
            "customer_code": customer.customer_code,
            "full_name": full_name,
            "email": customer.email,
            "phone": customer.phone,
            "status": customer.status,
            "priority": customer.priority,
            "profile": customer.profile,
            "customer_since": getattr(customer, 'first_policy_date', None),
            "total_policies": customer.total_policies,
            "total_premium": float(customer.total_premium),
        }
    
    def calculate_payment_insights(self, customer: Customer) -> Dict[str, Any]:
        """Calculate payment insights for a customer"""
        payments = CustomerPayment.objects.filter(
            customer=customer,
            is_deleted=False
        ).order_by('-payment_date')
        
        if not payments.exists():
            return self._get_empty_payment_insights()
        
        # Calculate basic metrics
        total_payments = payments.count()
        total_amount = sum(p.payment_amount for p in payments)
        avg_amount = total_amount / total_payments if total_payments > 0 else 0
        
        # Calculate on-time payment rate
        on_time_payments = payments.filter(
            payment_status='completed',
            payment_date__lte=models.F('due_date')
        ).count()
        on_time_rate = (on_time_payments / total_payments * 100) if total_payments > 0 else 0
        
        # Payment methods analysis
        payment_methods = payments.values_list('payment_mode', flat=True)
        method_counts = Counter(payment_methods)
        most_used_mode = method_counts.most_common(1)[0][0] if method_counts else 'unknown'
        
        # Payment timing analysis
        timing_analysis = self._analyze_payment_timing(payments)
        
        # Customer since calculation - use first_policy_date for accuracy, fallback to first payment date
        customer_since_date = None
        if hasattr(customer, 'first_policy_date') and customer.first_policy_date:
            customer_since_date = customer.first_policy_date
        elif payments.exists():
            first_payment = payments.last()
            if first_payment and first_payment.payment_date:
                customer_since_date = first_payment.payment_date
        elif hasattr(customer, 'created_at') and customer.created_at:
            # Fallback to customer creation date if no policy or payment date available
            customer_since_date = customer.created_at.date() if isinstance(customer.created_at, datetime) else customer.created_at
        
        customer_since = self._calculate_customer_since(customer_since_date)
        
        # Payment reliability rating
        reliability = self._calculate_payment_reliability(on_time_rate, total_payments)
        
        insights = {
            "total_premiums_paid": float(total_amount),
            "on_time_payment_rate": round(on_time_rate, 1),
            "total_payments_made": total_payments,
            "most_used_mode": most_used_mode,
            "average_payment_timing": timing_analysis.get('average_timing', 'Unknown'),
            "payment_reliability": reliability,
            "preferred_payment_method": most_used_mode,
            "average_payment_amount": float(avg_amount),
            "customer_since_years": customer_since,
            "last_payment_date": payments.first().payment_date.isoformat() if payments.exists() and payments.first().payment_date else None,
            "payment_frequency": timing_analysis.get('frequency', 'Unknown'),
        }
        
        return insights
    
    def _get_empty_payment_insights(self) -> Dict[str, Any]:
        """Return empty payment insights structure"""
        return {
            "total_premiums_paid": 0.0,
            "on_time_payment_rate": 0.0,
            "total_payments_made": 0,
            "most_used_mode": "Unknown",
            "average_payment_timing": "No data",
            "payment_reliability": "Unknown",
            "preferred_payment_method": "Unknown",
            "average_payment_amount": 0.0,
            "customer_since_years": "0 months",
            "last_payment_date": None,
            "payment_frequency": "Unknown",
        }
    
    def _analyze_payment_timing(self, payments) -> Dict[str, Any]:
        """Analyze payment timing patterns"""
        if not payments.exists():
            return {"average_timing": "No data", "frequency": "Unknown"}
        
        # Calculate average days early/late
        timing_diffs = []
        for payment in payments:
            if payment.payment_date and hasattr(payment, 'due_date') and payment.due_date:
                # Ensure we're comparing dates, not datetimes
                payment_date_only = payment.payment_date.date()
                diff = (payment.due_date - payment_date_only).days
                timing_diffs.append(diff)
        
        if timing_diffs:
            avg_diff = sum(timing_diffs) / len(timing_diffs)
            if avg_diff > 0:
                timing = f"{int(avg_diff)} days early"
            elif avg_diff < 0:
                timing = f"{int(abs(avg_diff))} days late"
            else:
                timing = "On time"
        else:
            timing = "Unknown"
        
        # Determine frequency
        if len(payments) >= 12:
            frequency = "Regular"
        elif len(payments) >= 6:
            frequency = "Occasional"
        else:
            frequency = "Infrequent"
        
        return {
            "average_timing": timing,
            "frequency": frequency
        }
    
    def _calculate_customer_since(self, first_payment_date) -> str:
        """Calculate years or months since first payment/customer since date"""
        if not first_payment_date:
            return "0 months"
        
        if isinstance(first_payment_date, datetime):
            first_date = first_payment_date.date()
        else:
            first_date = first_payment_date
        
        delta = self.today - first_date
        total_days = delta.days
        
        if total_days < 0:
            return "0 months"
        
        # Calculate years and months more accurately
        years = total_days // 365
        remaining_days_after_years = total_days % 365
        
        # Calculate months more accurately (average month = 30.44 days)
        # For remaining days, convert to approximate months
        approximate_months = remaining_days_after_years // 30
        
        if years >= 1:
            # Show years when >= 1 year
            return f"{years} year{'s' if years > 1 else ''}"
        else:
            # Show months if less than a year
            if approximate_months < 1:
                # Less than 30 days, show in days
                if total_days == 0:
                    return "0 months"
                else:
                    return f"{total_days} day{'s' if total_days > 1 else ''}"
            else:
                return f"{approximate_months} month{'s' if approximate_months > 1 else ''}"
    
    def _calculate_payment_reliability(self, on_time_rate: float, total_payments: int) -> str:
        """Calculate payment reliability rating"""
        # If no payments, return Unknown
        if total_payments == 0:
            return "Unknown"
        
        # For 1-2 payments, provide initial rating based on on_time_rate
        # For 3+ payments, use standard rating
        if total_payments < 3:
            # With limited data, provide initial rating
            if on_time_rate >= 100:
                return "Excellent"
            elif on_time_rate >= 90:
                return "Good"
            elif on_time_rate >= 70:
                return "Average"
            else:
                return "Poor"
        elif on_time_rate >= 95:
            return "Excellent"
        elif on_time_rate >= 85:
            return "Good"
        elif on_time_rate >= 70:
            return "Average"
        else:
            return "Poor"
    
    
    def calculate_communication_insights(self, customer: Customer) -> Dict[str, Any]:
        """Calculate communication insights for a customer"""
        communications = CommunicationLog.objects.filter(
            customer=customer,
            is_deleted=False
        ).order_by('-communication_date')
        
        if not communications.exists():
            return self._get_empty_communication_insights()
        
        # Basic metrics
        total_communications = communications.count()
        last_contact = communications.first().communication_date if communications.exists() else None
        
        # Channel breakdown
        channel_breakdown = self._calculate_channel_breakdown(communications)
        
        # Response time analysis
        response_time = self._calculate_avg_response_time(communications)
        
        # Satisfaction rating (mock calculation based on successful communications)
        successful_comms = communications.filter(outcome__in=['successful', 'delivered', 'opened', 'replied'])
        satisfaction = (successful_comms.count() / total_communications * 5) if total_communications > 0 else 0
        
        # Preferred channel
        preferred_channel = max(channel_breakdown.items(), key=lambda x: x[1])[0] if channel_breakdown else 'email'
        
        # Communication frequency
        frequency = self._calculate_communication_frequency(communications)
        
        # Response rate
        responses = communications.filter(outcome__in=['replied', 'clicked'])
        response_rate = (responses.count() / total_communications * 100) if total_communications > 0 else 0
        
        # Escalation count
        escalations = communications.filter(outcome='escalated').count()
        
        # Detailed Communication Breakdown by Topic
        topic_breakdown = defaultdict(int)
        for comm in communications:
            content = comm.message_content.lower()
            found = False
            for topic, keywords in COMMUNICATION_TOPICS.items():
                if any(keyword in content for keyword in keywords):
                    topic_breakdown[topic] += 1
                    found = True
                    break
            if not found:
                 topic_breakdown['other'] += 1

        insights = {
            "total_communications": total_communications,
            "avg_response_time": round(response_time, 1),
            "satisfaction_rating": round(satisfaction, 1),
            "last_contact_date": last_contact.isoformat() if last_contact else None,
            "channel_breakdown": channel_breakdown,
            "topic_breakdown": dict(topic_breakdown),
            "preferred_channel": preferred_channel,
            "communication_frequency": frequency,
            "response_rate": round(response_rate, 1),
            "escalation_count": escalations,
        }
        
        return insights
    
    def _get_empty_communication_insights(self) -> Dict[str, Any]:
        """Return empty communication insights structure"""
        return {
            "total_communications": 0,
            "avg_response_time": 0.0,
            "satisfaction_rating": 0.0,
            "last_contact_date": None,
            "channel_breakdown": {},
            "topic_breakdown": {},
            "preferred_channel": "Unknown",
            "communication_frequency": "Unknown",
            "response_rate": 0.0,
            "escalation_count": 0,
        }
    
    def _calculate_channel_breakdown(self, communications) -> Dict[str, int]:
        """Calculate communication breakdown by channel"""
        channel_counts = communications.values('channel').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        return {item['channel']: item['count'] for item in channel_counts}
    
    def _calculate_avg_response_time(self, communications) -> float:
        """Calculate average response time in hours"""
        successful_comms = communications.filter(outcome__in=['successful', 'replied'])
        if successful_comms.exists():
            # Mock calculation - assume 2.1 hours average
            return 2.1
        return 0.0
    
    def _calculate_communication_frequency(self, communications) -> str:
        """Calculate communication frequency pattern"""
        total = communications.count()
        if total >= 20:
            return "High"
        elif total >= 10:
            return "Medium"
        elif total >= 5:
            return "Low"
        else:
            return "Very Low"
    
    
    def calculate_claims_insights(self, customer: Customer) -> Dict[str, Any]:
        """Calculate real claims insights from PolicyClaim data"""
        
        claims = PolicyClaim.objects.filter(policy__customer=customer)
        
        if not claims.exists():
            return self._get_empty_claims_insights()
        
        # Real calculations based on actual claims data
        total_claims = claims.count()
        approved_claims = claims.filter(status='approved')
        rejected_claims = claims.filter(status='rejected')
        pending_claims = claims.filter(status__in=['submitted', 'pending'])
        
        total_claimed_amount = sum(claim.claim_amount for claim in claims)
        approved_amount = sum(claim.approved_amount for claim in approved_claims)
        
        # Calculate approval rate
        approval_rate = (approved_claims.count() / total_claims * 100) if total_claims > 0 else 0
        
        # Group by claim type
        claims_by_type = {}
        for claim in claims:
            claim_type = claim.claim_type
            claims_by_type[claim_type] = claims_by_type.get(claim_type, 0) + 1
        
        # Group by status
        claims_by_status = {
            'approved': approved_claims.count(),
            'rejected': rejected_claims.count(),
            'pending': pending_claims.count()
        }
        
        # Calculate average processing time (simplified - using claim_date to incident_date difference)
        processing_times = []
        for claim in approved_claims:
            if claim.claim_date and claim.incident_date:
                processing_days = (claim.claim_date - claim.incident_date).days
                if processing_days > 0:
                    processing_times.append(processing_days)
        
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 8
        
        # Determine risk level based on claim frequency and amounts
        if total_claims >= 5 or total_claimed_amount > 100000:
            risk_level = "medium"
        elif total_claims >= 3 or total_claimed_amount > 50000:
            risk_level = "low"
        else:
            risk_level = "very_low"
        
        # Determine claim frequency
        if total_claims >= 5:
            claim_frequency = "High"
        elif total_claims >= 3:
            claim_frequency = "Medium"
        else:
            claim_frequency = "Low"

        # Summary Breakdown for Claims (Amount/Year)
        summary_claims_breakdown = []
        # Get top 2 approved claims by amount for the summary view
        top_claims = approved_claims.order_by('-approved_amount')[:2]
        for claim in top_claims:
            summary_claims_breakdown.append({
                "type": claim.claim_type,
                "year": claim.incident_date.year,
                "amount": float(claim.approved_amount)
            })
        
        return {
            "total_claims": total_claims,
            "approved_amount": float(approved_amount),
            "total_claimed_amount": float(total_claimed_amount),
            "approval_rate": round(approval_rate, 1),
            "claims_by_type": claims_by_type,
            "claims_by_status": claims_by_status,
            "claims_summary_breakdown": summary_claims_breakdown,
            "last_claim_date": claims.first().incident_date.isoformat() if claims.exists() else None,
            "avg_processing_time": round(avg_processing_time, 1),
            "claim_frequency": claim_frequency,
            "risk_level": risk_level
        }
    
    def calculate_profile_insights(self, customer: Customer) -> Dict[str, Any]:
        """Calculate comprehensive customer profile insights"""
        policies = Policy.objects.filter(customer=customer, is_deleted=False)
        active_policies = policies.filter(status='active').count()
        expired_policies = policies.filter(status__in=['expired', 'cancelled']).count()
        
        family_policies = policies.filter(
        ).count()
        
        # Customer value calculations
        total_premium = sum(p.premium_amount for p in policies)
        ytd_payments = CustomerPayment.objects.filter(
            customer=customer,
            payment_date__year=self.now.year,
            is_deleted=False
        ).aggregate(total=models.Sum('payment_amount'))['total'] or 0
        
        # Customer segment (based on policy count and premium)
        if active_policies >= 3 and total_premium >= 50000:
            segment = "HNI"
        elif active_policies >= 2:
            segment = "Premium"
        else:
            segment = "Standard"
        
        # Engagement level
        recent_communications = CommunicationLog.objects.filter(
            customer=customer,
            communication_date__gte=self.now - timedelta(days=30),
            is_deleted=False
        ).count()
        
        if recent_communications >= 5:
            engagement = "High"
        elif recent_communications >= 2:
            engagement = "Medium"
        else:
            engagement = "Low"
        
        # Policy portfolio breakdown
        portfolio = {}
        for policy in policies:
            # Check if policy_type exists before accessing .name
            policy_type_name = policy.policy_type.name if policy.policy_type else 'Unknown'
            if policy_type_name not in portfolio:
                portfolio[policy_type_name] = 0
            portfolio[policy_type_name] += 1
        
        # Risk score calculation (simplified)
        risk_score = self._calculate_risk_score(customer, policies)
        
        insights = {
            "active_policies": active_policies,
            "family_policies": family_policies,
            "expired_lapsed_policies": expired_policies,
            "customer_lifetime_value": float(total_premium),
            "total_paid_ytd": float(ytd_payments),
            "customer_segment": segment,
            "engagement_level": engagement,
            "policy_portfolio": portfolio,
            "overall_risk_score": risk_score,
        }
        
        return insights
    
    def _calculate_risk_score(self, customer: Customer, policies) -> float:
        """Calculate overall risk score (0-100)"""
        score = 50.0 
        
        # Adjust based on payment history
        payments = CustomerPayment.objects.filter(customer=customer, is_deleted=False)
        if payments.exists():
            on_time_rate = payments.filter(payment_status='completed').count() / payments.count() * 100
            if on_time_rate >= 95:
                score -= 10
            elif on_time_rate < 70:
                score += 15
        
        if policies.count() > 3:
            score -= 5 
        
        # Adjust based on customer age
        if hasattr(customer, 'first_policy_date') and customer.first_policy_date:
            years_as_customer = (self.today - customer.first_policy_date).days // 365
            if years_as_customer > 5:
                score -= 10 
        
        return max(0, min(100, score))
    
    
    def get_payment_schedule(self, customer: Customer) -> Dict[str, Any]:
        """Get upcoming payment schedule for customer"""
        upcoming_payments = PaymentSchedule.objects.filter(
            renewal_case__customer=customer,
            due_date__gte=self.today,
            status__in=['pending', 'scheduled'],
            is_deleted=False
        ).order_by('due_date')[:5]
        
        payments_data = []
        for payment in upcoming_payments:
            days_until_due = (payment.due_date - self.today).days
            payments_data.append({
                "amount": float(payment.amount_due),
                "due_date": payment.due_date.isoformat() if payment.due_date else None,
                "policy": payment.renewal_case.policy.policy_type.name if payment.renewal_case.policy.policy_type else "Unknown",
                "days_until_due": days_until_due,
                "status": payment.status,
            })
        
        return {
            "upcoming_payments": payments_data,
            "next_payment": payments_data[0] if payments_data else None,
        }
    
    def get_payment_history(self, customer: Customer, years: int = 10) -> Dict[str, Any]:
        """Get detailed payment history for customer"""
        start_date = self.today - timedelta(days=years * 365)
        
        payments = CustomerPayment.objects.filter(
            customer=customer,
            payment_date__gte=start_date,
            is_deleted=False
        ).select_related(
            'renewal_case',
            'renewal_case__policy',
            'renewal_case__policy__policy_type'
        ).order_by('-payment_date')
        
        # Group by year
        yearly_data = defaultdict(list)
        yearly_totals = defaultdict(float)
        
        for payment in payments:
            year = payment.payment_date.year
            
            # Get policy name from renewal_case -> policy -> policy_type
            policy_name = "Unknown"
            if payment.renewal_case and payment.renewal_case.policy:
                if payment.renewal_case.policy.policy_type:
                    policy_name = payment.renewal_case.policy.policy_type.name
                else:
                    policy_name = "Unknown Policy Type"
            elif payment.renewal_case:
                policy_name = "No Policy"
            
            yearly_data[year].append({
                "amount": float(payment.payment_amount),
                "date": payment.payment_date.isoformat() if payment.payment_date else None,
                "status": payment.payment_status,
                "mode": payment.payment_mode,
                "policy": policy_name,
            })
            yearly_totals[year] += float(payment.payment_amount)
        
        # Create yearly summary
        yearly_summary = []
        for year in sorted(yearly_data.keys(), reverse=True):
            payments_count = len(yearly_data[year])
            yearly_summary.append({
                "year": year,
                "total": yearly_totals[year],
                "payments_count": payments_count,
                "payments": yearly_data[year],
            })
        
        # Calculate 10-year summary
        total_premiums = sum(yearly_totals.values())
        total_payments = sum(len(payments) for payments in yearly_data.values())
        on_time_payments = payments.filter(payment_status='completed').count()
        on_time_rate = (on_time_payments / total_payments * 100) if total_payments > 0 else 0
        
        # Most used payment mode
        payment_modes = [p.payment_mode for p in payments]
        most_used_mode = Counter(payment_modes).most_common(1)[0][0] if payment_modes else 'Unknown'
        
        return {
            "yearly_breakdown": yearly_summary,
            "summary": {
                "total_premiums_paid": total_premiums,
                "on_time_payment_rate": round(on_time_rate, 1),
                "total_payments_made": total_payments,
                "most_used_mode": most_used_mode,
            }
        }
    
    def get_communication_history(self, customer: Customer) -> Dict[str, Any]:
        """Get detailed communication history"""
        communications = CommunicationLog.objects.filter(
            customer=customer,
            is_deleted=False
        ).select_related('created_by').order_by('-communication_date')
        
        channel_data = defaultdict(list)
        comm_list = []
        
        # Manually combine first and last name
        customer_name = f"{customer.first_name} {customer.last_name}".strip()
        customer_contact = customer.phone or customer.email
        
        for comm in communications:
            agent_name = "System"
            if comm.created_by:
                try:
                    # Manually combine first and last name for agent
                    name = f"{comm.created_by.first_name} {comm.created_by.last_name}".strip()
                    if name:
                        agent_name = name
                    else:
                        agent_name = comm.created_by.email
                except AttributeError:
                    agent_name = "System User"
            
            resolved = comm.outcome in ['successful', 'replied', 'resolved']
            summary = (comm.message_content[:75] + '...') if len(comm.message_content) > 75 else comm.message_content
            
            # Use getattr for safety, default to None
            duration = getattr(comm, 'duration_in_minutes', None)

            comm_data = {
                "id": comm.id,
                "date": comm.communication_date.isoformat() if comm.communication_date else None,
                "channel": comm.channel,
                "outcome": comm.outcome,
                "message_content": comm.message_content,
                "response_received": comm.response_received,
                "attachment_count": getattr(comm, 'attachment_count', 0), 
                "agent_name": agent_name, 
                "timeline_event": f"{comm.channel.capitalize()} - {comm.outcome.capitalize()}",
                
                # FIELDS YOU REQUESTED 
                "contact_name": customer_name,
                "contact_details": customer_contact,
                "communication_summary": summary,
                "inbound": True,  
                "resolved": resolved,
                "priority": "Medium",
                "time": comm.communication_date.strftime('%I:%M %p') if comm.communication_date else None,
                "agent": agent_name,
                "duration": duration
            }
            channel_data[comm.channel].append(comm_data)
            comm_list.append(comm_data)
        
        return {
            "total_communications": communications.count(),
            "all_communications": comm_list,
            "by_channel": dict(channel_data),
        }
    
    def get_claims_history(self, customer: Customer) -> Dict[str, Any]:
        """Get detailed claims history (Dynamic implementation)"""
        
        # Use prefetch_related for the new timeline_events 
        claims = PolicyClaim.objects.filter(
            policy__customer=customer
        ).select_related(
            'assigned_to' 
        ).prefetch_related(
            'timeline_events' 
        ).order_by('-incident_date')
        
        claims_data = []
        for claim in claims:
            
            adjuster_name = "Not Assigned" 
            try:
                if claim.assigned_to:
                    user = claim.assigned_to 
                    # Manually combine first and last name for adjuster
                    name = f"{user.first_name} {user.last_name}".strip()
                    if name:
                        adjuster_name = name
                    else:
                        adjuster_name = user.email
            except Exception:
                pass 

            # Build the REAL timeline_events list )
            timeline_events = []
            if ClaimTimelineEvent:
                timeline_events = [
                    {
                        "date": event.event_date.isoformat(), 
                        "event": event.event_name, 
                        "status": event.status
                    } 
                    for event in claim.timeline_events.all() 
                ]
            

            claims_data.append({
                "id": claim.id,
                "title": claim.claim_type,
                "type": claim.claim_type,
                "status": claim.status,
                "claim_amount": float(claim.claim_amount),
                "approved_amount": float(claim.approved_amount),
                "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
                "claim_number": claim.claim_number,
                "adjuster": adjuster_name, 
                "rejection_reason": claim.rejection_reason,
                "timeline_events": timeline_events, 
                "document_attachments": getattr(claim, 'document_count', 0),
                "priority": "Medium" # MOCKED
            })
        
        summary = {
            "total_claims": claims.count(),
            "approved_claims": claims.filter(status='approved').count(),
            "rejected_claims": claims.filter(status='rejected').count(),
            "pending_claims": claims.filter(status__in=['submitted', 'pending']).count(),
        }
        
        return {
            "claims": claims_data,
            "summary": summary
        }
    
    def _get_empty_claims_insights(self) -> Dict[str, Any]:
        """Return empty claims insights structure"""
        return {
            "total_claims": 0,
            "approved_amount": 0.0,
            "total_claimed_amount": 0.0,
            "approval_rate": 0.0,
            "claims_by_type": {},
            "claims_by_status": {
                "approved": 0,
                "rejected": 0,
                "pending": 0
            },
            "claims_summary_breakdown": [],
            "last_claim_date": None,
            "avg_processing_time": 0,
            "claim_frequency": "None",
            "risk_level": "very_low"
        }
