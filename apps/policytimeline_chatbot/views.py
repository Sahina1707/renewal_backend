from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db.models import Q
from .models import PolicyTimelineChatbot, PolicyTimelineChatbotMessage


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_suggestions(request):
    """
    Get quick suggestions for policy timeline chatbot
    """
    suggestions = [
        "Show me my policy timeline events",
        "What are my upcoming policy renewals?",
        "Tell me about my payment history",
        "What is my policy coverage details?",
        "Show me my policy premium changes over time",
        "What are my policy modification events?",
        "Tell me about my claim history",
        "What communication events do I have?",
        "Show me my policy creation timeline",
        "What are my policy preferences?",
        "Tell me about my customer profile",
        "What is my policy age and tenure?",
        "What is my financial status?",
        "Show me my financial profile",
        "What is my annual income?",
        "What is my risk profile?",
        "What are my assets?",
        "Show me my customer assets",
        "What assets do I own?",
        "Tell me about my property",
        "What is my family medical history?",
        "Show me my medical history",
        "What are my family medical conditions?",
        "Tell me about my health history",
        "What are my family medical history details?",
        "Tell me about my other insurance policies"
    ]
    
    return Response({
        'suggestions': suggestions,
        'message': 'Quick suggestions for policy timeline analysis'
    })


def get_policy_timeline_context(customer_id=None, policy_id=None, user=None):
    """
    Get context data from policy timeline related tables for AI response
    """
    try:
        context_data = {
            'customer_info': {},
            'policy_info': {},
            'timeline_events': [],
            'payment_history': [],
            'financial_profile': {},
            'customer_assets': [],
            'family_medical_history': {},
            'renewal_info': [],
            'preferences': {}
        }
        
        try:
            from apps.customers.models import Customer
            if customer_id:
                customer = Customer.objects.filter(customer_id=customer_id).first()
                if customer:
                    context_data['customer_info'] = {
                        'customer_id': getattr(customer, 'customer_id', 'N/A'),
                        'customer_name': getattr(customer, 'customer_name', 'N/A'),
                        'email': getattr(customer, 'email', 'N/A'),
                        'mobile': getattr(customer, 'mobile', 'N/A')
                    }
            else:
                customers = Customer.objects.all()[:5]
                for customer in customers:
                    context_data['customer_info'] = {
                        'customer_id': getattr(customer, 'customer_id', 'N/A'),
                        'customer_name': getattr(customer, 'customer_name', 'N/A'),
                        'email': getattr(customer, 'email', 'N/A'),
                        'mobile': getattr(customer, 'mobile', 'N/A')
                    }
                    break  
        except Exception:
            pass
        
        try:
            from apps.policies.models import Policy
            if policy_id:
                policy = Policy.objects.filter(policy_id=policy_id).first()
                if policy:
                    context_data['policy_info'] = {
                        'policy_id': getattr(policy, 'policy_id', 'N/A'),
                        'policy_type': getattr(policy, 'policy_type', 'N/A'),
                        'premium': getattr(policy, 'premium', 'N/A'),
                        'start_date': getattr(policy, 'start_date', 'N/A'),
                        'end_date': getattr(policy, 'end_date', 'N/A'),
                        'status': getattr(policy, 'status', 'N/A')
                    }
            else:
                policies = Policy.objects.all()[:5]
                for policy in policies:
                    context_data['policy_info'] = {
                        'policy_id': getattr(policy, 'policy_id', 'N/A'),
                        'policy_type': getattr(policy, 'policy_type', 'N/A'),
                        'premium': getattr(policy, 'premium', 'N/A'),
                        'start_date': getattr(policy, 'start_date', 'N/A'),
                        'end_date': getattr(policy, 'end_date', 'N/A'),
                        'status': getattr(policy, 'status', 'N/A')
                    }
                    break  
        except Exception:
            pass
        
        try:
            from apps.policy_timeline.models import PolicyTimeline
            timeline_events = PolicyTimeline.objects.all()[:10]
            for event in timeline_events:
                context_data['timeline_events'].append({
                    'event_type': getattr(event, 'event_type', 'N/A'),
                    'event_date': getattr(event, 'event_date', 'N/A'),
                    'description': getattr(event, 'description', 'N/A'),
                    'agent': getattr(event, 'agent', 'N/A')
                })
        except Exception:
            pass
        
        try:
            from apps.customer_payment_schedule.models import PaymentSchedule
            payments = PaymentSchedule.objects.all()[:5]
            for payment in payments:
                context_data['payment_history'].append({
                    'amount': getattr(payment, 'amount', 'N/A'),
                    'due_date': getattr(payment, 'due_date', 'N/A'),
                    'status': getattr(payment, 'status', 'N/A'),
                    'payment_method': getattr(payment, 'payment_method', 'N/A')
                })
        except Exception:
            pass
        
        try:
            from apps.customer_payments.models import CustomerPayment
            if user and hasattr(user, 'id'):
                try:
                    from apps.customers.models import Customer
                    customer = Customer.objects.filter(
                        Q(user_id=user.id) | Q(email=user.email) | Q(user__id=user.id)
                    ).first()
                    
                    if customer:
                        customer_payments = CustomerPayment.objects.filter(
                            customer_id=customer.customer_id
                        ).order_by('-payment_date')[:10]
                        
                        if customer_payments.exists():
                            for payment in customer_payments:
                                context_data['payment_history'].append({
                                    'amount': getattr(payment, 'amount', 'N/A'),
                                    'payment_date': getattr(payment, 'payment_date', 'N/A'),
                                    'status': getattr(payment, 'status', 'N/A'),
                                    'payment_method': getattr(payment, 'payment_method', 'N/A'),
                                    'transaction_id': getattr(payment, 'transaction_id', 'N/A'),
                                    'policy_id': getattr(payment, 'policy_id', 'N/A'),
                                    'customer_id': getattr(payment, 'customer_id', 'N/A')
                                })
                        else:
                            context_data['payment_history'] = []
                            context_data['no_payments_found'] = True
                            context_data['customer_id'] = customer.customer_id
                    else:
                        customer_payments = CustomerPayment.objects.all()[:10]
                        for payment in customer_payments:
                            context_data['payment_history'].append({
                                'amount': getattr(payment, 'amount', 'N/A'),
                                'payment_date': getattr(payment, 'payment_date', 'N/A'),
                                'status': getattr(payment, 'status', 'N/A'),
                                'payment_method': getattr(payment, 'payment_method', 'N/A'),
                                'transaction_id': getattr(payment, 'transaction_id', 'N/A'),
                                'policy_id': getattr(payment, 'policy_id', 'N/A')
                            })
                except Exception:
                    customer_payments = CustomerPayment.objects.all()[:10]
                    for payment in customer_payments:
                        context_data['payment_history'].append({
                            'amount': getattr(payment, 'amount', 'N/A'),
                            'payment_date': getattr(payment, 'payment_date', 'N/A'),
                            'status': getattr(payment, 'status', 'N/A'),
                            'payment_method': getattr(payment, 'payment_method', 'N/A'),
                            'transaction_id': getattr(payment, 'transaction_id', 'N/A'),
                            'policy_id': getattr(payment, 'policy_id', 'N/A')
                        })
            else:
                customer_payments = CustomerPayment.objects.all()[:10]
                for payment in customer_payments:
                    context_data['payment_history'].append({
                        'amount': getattr(payment, 'amount', 'N/A'),
                        'payment_date': getattr(payment, 'payment_date', 'N/A'),
                        'status': getattr(payment, 'status', 'N/A'),
                        'payment_method': getattr(payment, 'payment_method', 'N/A'),
                        'transaction_id': getattr(payment, 'transaction_id', 'N/A'),
                        'policy_id': getattr(payment, 'policy_id', 'N/A')
                    })
        except Exception:
            pass
        
        # Try to get customer financial profile information - prioritize authenticated user's data
        try:
            from apps.customer_financial_profile.models import CustomerFinancialProfile
            if user and hasattr(user, 'id'):
                try:
                    from apps.customers.models import Customer
                    customer = Customer.objects.filter(
                        Q(user_id=user.id) | Q(email=user.email) | Q(user__id=user.id)
                    ).first()
                    
                    if customer:
                        # Fetch financial profile for this specific customer
                        financial_profile = CustomerFinancialProfile.objects.filter(
                            customer_id=customer.customer_id
                        ).first()
                        
                        if financial_profile:
                            context_data['financial_profile'] = {
                                'annual_income': getattr(financial_profile, 'annual_income', 'N/A'),
                                'employment_status': getattr(financial_profile, 'employment_status', 'N/A'),
                                'occupation': getattr(financial_profile, 'occupation', 'N/A'),
                                'company_name': getattr(financial_profile, 'company_name', 'N/A'),
                                'risk_profile': getattr(financial_profile, 'risk_profile', 'N/A'),
                                'investment_experience': getattr(financial_profile, 'investment_experience', 'N/A'),
                                'financial_goals': getattr(financial_profile, 'financial_goals', 'N/A'),
                                'customer_id': getattr(financial_profile, 'customer_id', 'N/A')
                            }
                        else:
                            # No financial profile found for this customer
                            context_data['financial_profile'] = {}
                            context_data['no_financial_profile_found'] = True
                            context_data['customer_id'] = customer.customer_id
                    else:
                        # Customer not found, get general data
                        financial_profiles = CustomerFinancialProfile.objects.all()[:5]
                        for profile in financial_profiles:
                            context_data['financial_profile'] = {
                                'annual_income': getattr(profile, 'annual_income', 'N/A'),
                                'employment_status': getattr(profile, 'employment_status', 'N/A'),
                                'occupation': getattr(profile, 'occupation', 'N/A'),
                                'company_name': getattr(profile, 'company_name', 'N/A'),
                                'risk_profile': getattr(profile, 'risk_profile', 'N/A'),
                                'investment_experience': getattr(profile, 'investment_experience', 'N/A'),
                                'financial_goals': getattr(profile, 'financial_goals', 'N/A')
                            }
                            break
                except Exception:
                    # Fallback to general data
                    financial_profiles = CustomerFinancialProfile.objects.all()[:5]
                    for profile in financial_profiles:
                        context_data['financial_profile'] = {
                            'annual_income': getattr(profile, 'annual_income', 'N/A'),
                            'employment_status': getattr(profile, 'employment_status', 'N/A'),
                            'occupation': getattr(profile, 'occupation', 'N/A'),
                            'company_name': getattr(profile, 'company_name', 'N/A'),
                            'risk_profile': getattr(profile, 'risk_profile', 'N/A'),
                            'investment_experience': getattr(profile, 'investment_experience', 'N/A'),
                            'financial_goals': getattr(profile, 'financial_goals', 'N/A')
                        }
                        break
            else:
                # No user provided, get general data
                financial_profiles = CustomerFinancialProfile.objects.all()[:5]
                for profile in financial_profiles:
                    context_data['financial_profile'] = {
                        'annual_income': getattr(profile, 'annual_income', 'N/A'),
                        'employment_status': getattr(profile, 'employment_status', 'N/A'),
                        'occupation': getattr(profile, 'occupation', 'N/A'),
                        'company_name': getattr(profile, 'company_name', 'N/A'),
                        'risk_profile': getattr(profile, 'risk_profile', 'N/A'),
                        'investment_experience': getattr(profile, 'investment_experience', 'N/A'),
                        'financial_goals': getattr(profile, 'financial_goals', 'N/A')
                    }
                    break
        except Exception:
            pass
        
        # Try to get customer assets information - prioritize authenticated user's data
        try:
            from apps.customer_assets.models import CustomerAssets
            if user and hasattr(user, 'id'):
                try:
                    from apps.customers.models import Customer
                    customer = Customer.objects.filter(
                        Q(user_id=user.id) | Q(email=user.email) | Q(user__id=user.id)
                    ).first()
                    
                    if customer:
                        # Fetch assets for this specific customer
                        customer_assets = CustomerAssets.objects.filter(
                            customer_id=customer.customer_id
                        ).order_by('-created_at')[:10]
                        
                        if customer_assets.exists():
                            for asset in customer_assets:
                                context_data['customer_assets'].append({
                                    'asset_type': getattr(asset, 'asset_type', 'N/A'),
                                    'asset_name': getattr(asset, 'asset_name', 'N/A'),
                                    'asset_value': getattr(asset, 'asset_value', 'N/A'),
                                    'purchase_date': getattr(asset, 'purchase_date', 'N/A'),
                                    'location': getattr(asset, 'location', 'N/A'),
                                    'description': getattr(asset, 'description', 'N/A'),
                                    'customer_id': getattr(asset, 'customer_id', 'N/A')
                                })
                        else:
                            # No assets found for this customer
                            context_data['customer_assets'] = []
                            context_data['no_assets_found'] = True
                            context_data['customer_id'] = customer.customer_id
                    else:
                        # Customer not found, get general data
                        assets = CustomerAssets.objects.all()[:10]
                        for asset in assets:
                            context_data['customer_assets'].append({
                                'asset_type': getattr(asset, 'asset_type', 'N/A'),
                                'asset_name': getattr(asset, 'asset_name', 'N/A'),
                                'asset_value': getattr(asset, 'asset_value', 'N/A'),
                                'purchase_date': getattr(asset, 'purchase_date', 'N/A'),
                                'location': getattr(asset, 'location', 'N/A'),
                                'description': getattr(asset, 'description', 'N/A')
                            })
                except Exception:
                    # Fallback to general data
                    assets = CustomerAssets.objects.all()[:10]
                    for asset in assets:
                        context_data['customer_assets'].append({
                            'asset_type': getattr(asset, 'asset_type', 'N/A'),
                            'asset_name': getattr(asset, 'asset_name', 'N/A'),
                            'asset_value': getattr(asset, 'asset_value', 'N/A'),
                            'purchase_date': getattr(asset, 'purchase_date', 'N/A'),
                            'location': getattr(asset, 'location', 'N/A'),
                            'description': getattr(asset, 'description', 'N/A')
                        })
            else:
                # No user provided, get general data
                assets = CustomerAssets.objects.all()[:10]
                for asset in assets:
                    context_data['customer_assets'].append({
                        'asset_type': getattr(asset, 'asset_type', 'N/A'),
                        'asset_name': getattr(asset, 'asset_name', 'N/A'),
                        'asset_value': getattr(asset, 'asset_value', 'N/A'),
                        'purchase_date': getattr(asset, 'purchase_date', 'N/A'),
                        'location': getattr(asset, 'location', 'N/A'),
                        'description': getattr(asset, 'description', 'N/A')
                    })
        except Exception:
            pass
        
        # Try to get customer family medical history information - prioritize authenticated user's data
        try:
            from apps.customer_family_medical_history.models import CustomerFamilyMedicalHistory
            if user and hasattr(user, 'id'):
                try:
                    from apps.customers.models import Customer
                    customer = Customer.objects.filter(
                        Q(user_id=user.id) | Q(email=user.email) | Q(user__id=user.id)
                    ).first()
                    
                    if customer:
                        # Fetch family medical history for this specific customer
                        family_medical_history = CustomerFamilyMedicalHistory.objects.filter(
                            customer_id=customer.customer_id
                        ).first()
                        
                        if family_medical_history:
                            context_data['family_medical_history'] = {
                                'diabetes': getattr(family_medical_history, 'diabetes', 'N/A'),
                                'heart_disease': getattr(family_medical_history, 'heart_disease', 'N/A'),
                                'cancer': getattr(family_medical_history, 'cancer', 'N/A'),
                                'hypertension': getattr(family_medical_history, 'hypertension', 'N/A'),
                                'stroke': getattr(family_medical_history, 'stroke', 'N/A'),
                                'mental_health': getattr(family_medical_history, 'mental_health', 'N/A'),
                                'genetic_disorders': getattr(family_medical_history, 'genetic_disorders', 'N/A'),
                                'life_expectancy': getattr(family_medical_history, 'life_expectancy', 'N/A'),
                                'customer_id': getattr(family_medical_history, 'customer_id', 'N/A')
                            }
                        else:
                            # No family medical history found for this customer
                            context_data['family_medical_history'] = {}
                            context_data['no_family_medical_history_found'] = True
                            context_data['customer_id'] = customer.customer_id
                    else:
                        # Customer not found, get general data
                        family_medical_histories = CustomerFamilyMedicalHistory.objects.all()[:5]
                        for history in family_medical_histories:
                            context_data['family_medical_history'] = {
                                'diabetes': getattr(history, 'diabetes', 'N/A'),
                                'heart_disease': getattr(history, 'heart_disease', 'N/A'),
                                'cancer': getattr(history, 'cancer', 'N/A'),
                                'hypertension': getattr(history, 'hypertension', 'N/A'),
                                'stroke': getattr(history, 'stroke', 'N/A'),
                                'mental_health': getattr(history, 'mental_health', 'N/A'),
                                'genetic_disorders': getattr(history, 'genetic_disorders', 'N/A'),
                                'life_expectancy': getattr(history, 'life_expectancy', 'N/A')
                            }
                            break
                except Exception:
                    # Fallback to general data
                    family_medical_histories = CustomerFamilyMedicalHistory.objects.all()[:5]
                    for history in family_medical_histories:
                        context_data['family_medical_history'] = {
                            'diabetes': getattr(history, 'diabetes', 'N/A'),
                            'heart_disease': getattr(history, 'heart_disease', 'N/A'),
                            'cancer': getattr(history, 'cancer', 'N/A'),
                            'hypertension': getattr(history, 'hypertension', 'N/A'),
                            'stroke': getattr(history, 'stroke', 'N/A'),
                            'mental_health': getattr(history, 'mental_health', 'N/A'),
                            'genetic_disorders': getattr(history, 'genetic_disorders', 'N/A'),
                            'life_expectancy': getattr(history, 'life_expectancy', 'N/A')
                        }
                        break
            else:
                # No user provided, get general data
                family_medical_histories = CustomerFamilyMedicalHistory.objects.all()[:5]
                for history in family_medical_histories:
                    context_data['family_medical_history'] = {
                        'diabetes': getattr(history, 'diabetes', 'N/A'),
                        'heart_disease': getattr(history, 'heart_disease', 'N/A'),
                        'cancer': getattr(history, 'cancer', 'N/A'),
                        'hypertension': getattr(history, 'hypertension', 'N/A'),
                        'stroke': getattr(history, 'stroke', 'N/A'),
                        'mental_health': getattr(history, 'mental_health', 'N/A'),
                        'genetic_disorders': getattr(history, 'genetic_disorders', 'N/A'),
                        'life_expectancy': getattr(history, 'life_expectancy', 'N/A')
                    }
                    break
        except Exception:
            pass
        
        try:
            from apps.customer_policy_preferences.models import CustomerPolicyPreference
            preferences = CustomerPolicyPreference.objects.all()[:5]
            for pref in preferences:
                context_data['preferences'] = {
                    'preferred_policy_types': getattr(pref, 'preferred_policy_types', 'N/A'),
                    'max_budget': getattr(pref, 'max_budget', 'N/A'),
                    'avoided_types': getattr(pref, 'avoided_types', 'N/A')
                }
                break 
        except Exception:
            pass
        
        return context_data
        
    except Exception as e:
        return {
            'customer_info': {},
            'policy_info': {},
            'timeline_events': [],
            'payment_history': [],
            'financial_profile': {},
            'customer_assets': [],
            'family_medical_history': {},
            'renewal_info': [],
            'preferences': {},
            'error': str(e)
        }


def is_policy_timeline_related_question(message):
    """
    Check if the question is related to policy timeline
    """
    policy_keywords = [
        'policy', 'timeline', 'renewal', 'premium', 'coverage', 'payment', 
        'customer', 'profile', 'preference', 'medical', 'history', 'claim',
        'modification', 'creation', 'communication', 'schedule', 'due',
        'financial', 'family', 'insurance', 'tenure', 'age', 'events',
        'income', 'employment', 'occupation', 'risk', 'investment', 'goals',
        'status', 'salary', 'company', 'job', 'work', 'assets', 'asset',
        'property', 'vehicle', 'house', 'car', 'home', 'belongings', 'possessions',
        'health', 'diabetes', 'heart', 'cancer', 'hypertension', 'stroke',
        'mental', 'genetic', 'disorders', 'life', 'expectancy', 'conditions'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in policy_keywords)


def generate_ai_response(user_message, context_data):
    """
    Generate AI response using OpenAI API
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        context_summary = []
        
        if context_data.get('customer_info'):
            context_summary.append(f"Customer: {context_data['customer_info'].get('customer_name', 'N/A')} (ID: {context_data['customer_info'].get('customer_id', 'N/A')})")
        
        if context_data.get('policy_info'):
            context_summary.append(f"Policy: {context_data['policy_info'].get('policy_type', 'N/A')} (Premium: ₹{context_data['policy_info'].get('premium', 'N/A')})")
        
        if context_data.get('timeline_events'):
            context_summary.append(f"Timeline Events: {len(context_data['timeline_events'])} events available")
        
        if context_data.get('payment_history'):
            context_summary.append(f"Payment History: {len(context_data['payment_history'])} payment records")
            if context_data['payment_history']:
                sample_payment = context_data['payment_history'][0]
                context_summary.append(f"Sample Payment: ₹{sample_payment.get('amount', 'N/A')} on {sample_payment.get('payment_date', sample_payment.get('due_date', 'N/A'))}")
        elif context_data.get('no_payments_found'):
            context_summary.append(f"No payment records found for customer ID: {context_data.get('customer_id', 'N/A')}")
        
        if context_data.get('financial_profile'):
            context_summary.append(f"Financial Profile: Available")
            if context_data['financial_profile'].get('annual_income'):
                context_summary.append(f"Annual Income: ₹{context_data['financial_profile'].get('annual_income', 'N/A')}")
            if context_data['financial_profile'].get('risk_profile'):
                context_summary.append(f"Risk Profile: {context_data['financial_profile'].get('risk_profile', 'N/A')}")
        elif context_data.get('no_financial_profile_found'):
            context_summary.append(f"No financial profile found for customer ID: {context_data.get('customer_id', 'N/A')}")
        
        if context_data.get('customer_assets'):
            context_summary.append(f"Customer Assets: {len(context_data['customer_assets'])} assets")
            if context_data['customer_assets']:
                sample_asset = context_data['customer_assets'][0]
                context_summary.append(f"Sample Asset: {sample_asset.get('asset_name', 'N/A')} (₹{sample_asset.get('asset_value', 'N/A')})")
        elif context_data.get('no_assets_found'):
            context_summary.append(f"No assets found for customer ID: {context_data.get('customer_id', 'N/A')}")
        
        if context_data.get('family_medical_history'):
            context_summary.append(f"Family Medical History: Available")
            if context_data['family_medical_history'].get('diabetes') != 'N/A':
                context_summary.append(f"Diabetes: {context_data['family_medical_history'].get('diabetes', 'N/A')}")
            if context_data['family_medical_history'].get('heart_disease') != 'N/A':
                context_summary.append(f"Heart Disease: {context_data['family_medical_history'].get('heart_disease', 'N/A')}")
            if context_data['family_medical_history'].get('life_expectancy') != 'N/A':
                context_summary.append(f"Life Expectancy: {context_data['family_medical_history'].get('life_expectancy', 'N/A')} years")
        elif context_data.get('no_family_medical_history_found'):
            context_summary.append(f"No family medical history found for customer ID: {context_data.get('customer_id', 'N/A')}")
        
        if context_data.get('preferences'):
            context_summary.append(f"Customer Preferences: Available")
        
        context_text = f"""
        You are a helpful AI assistant for an insurance policy timeline management system. 
        You specialize in analyzing policy timelines, customer profiles, and policy-related data.
        
        Current policy timeline context:
        {chr(10).join(context_summary) if context_summary else "General policy timeline data available"}
        
        User question: {user_message}
        
        Please provide a helpful, professional response based on the context provided.
        If you have specific payment history data, use it to provide detailed information about payments, amounts, dates, and methods.
        If you have specific financial profile data, use it to provide detailed information about income, employment, risk profile, and financial goals.
        If you have specific customer assets data, use it to provide detailed information about asset types, names, values, purchase dates, and locations.
        If you have specific family medical history data, use it to provide detailed information about medical conditions, family history, and life expectancy.
        If no payment records are found for the customer, inform them politely that no payment history is available and suggest they contact their insurance provider or check their account.
        If no financial profile is found for the customer, inform them politely that no financial details are available and suggest they contact their insurance provider to update their profile.
        If no assets are found for the customer, inform them politely that no asset information is available and suggest they contact their insurance provider to update their asset details.
        If no family medical history is found for the customer, inform them politely that no medical history is available and suggest they contact their insurance provider to update their medical profile.
        If you have specific data, use it. If not, provide general guidance about policy renewals, timelines, and insurance management.
        Keep responses concise but informative and always be helpful.
        """
        
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert insurance policy timeline management assistant specializing in policy analysis and customer insights."},
                {"role": "user", "content": context_text}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"I apologize, but I'm currently unable to process your request due to a technical issue. Please try again later."


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_request_get_response(request):
    """
    Send a request to chatbot and get AI response
    """
    user_message = request.data.get('message', '')
    
    if not user_message:
        return Response({
            'error': 'Message is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not is_policy_timeline_related_question(user_message):
        return Response({
            'response': "I'm sorry, but I'm specifically designed to help with policy timeline analysis and insurance policy management. Please ask me questions related to:\n\n• Policy timeline events\n• Policy renewals and payments\n• Customer profile and preferences\n• Policy coverage details\n• Payment schedules and history\n• Policy modifications and claims\n• Family medical history\n• Financial profile analysis\n\nHow can I assist you with your policy timeline today?"
        }, status=status.HTTP_200_OK)
    
    chatbot_session, created = PolicyTimelineChatbot.objects.get_or_create(
        customer_id=request.data.get('customer_id', 'DEFAULT'),
        defaults={
            'customer_name': request.data.get('customer_name', 'Anonymous'),
            'policy_id': request.data.get('policy_id', 'N/A'),
            'policy_type': request.data.get('policy_type', 'General'),
            'policy_premium': request.data.get('policy_premium', 0),
            'policy_start_date': request.data.get('policy_start_date', '2024-01-01'),
            'policy_age': request.data.get('policy_age', 0),
            'chatbot_session_id': f"session_{request.user.id}_{request.data.get('customer_id', 'default')}",
            'is_active': True
        }
    )
    
    user_msg = PolicyTimelineChatbotMessage.objects.create(
        chatbot_session=chatbot_session,
        message_type='user',
        content=user_message
    )
    
    context_data = get_policy_timeline_context(
        customer_id=request.data.get('customer_id'),
        policy_id=request.data.get('policy_id'),
        user=request.user
    )
    
    print(f"DEBUG: Context data fetched: {context_data}")
    
    ai_response = generate_ai_response(user_message, context_data)
    
    ai_msg = PolicyTimelineChatbotMessage.objects.create(
        chatbot_session=chatbot_session,
        message_type='bot',
        content=ai_response
    )
    
    chatbot_session.interaction_count += 1
    chatbot_session.save()
    
    return Response({
        'response': ai_response
    }, status=status.HTTP_200_OK)
