from rest_framework import serializers
from .models import CustomerFamilyMedicalHistory
class CustomerFamilyMedicalHistorySerializer(serializers.ModelSerializer):
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    risk_score = serializers.IntegerField(read_only=True)
    is_high_risk = serializers.BooleanField(read_only=True)
    requires_medical_exam = serializers.BooleanField(read_only=True)
    suggested_premium_loading = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    condition_summary = serializers.CharField(read_only=True)
    treatment_summary = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerFamilyMedicalHistory
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'customer_email',
            'condition_category',
            'condition_name',
            'condition_status',
            'family_relation',
            'age_diagnosed',
            'severity_level',
            'current_medication',
            'last_checkup_date',
            'doctor_name',
            'hospital_name',
            'insurance_impact',
            'premium_loading',
            'notes',
            'is_active',
            'risk_score',
            'is_high_risk',
            'requires_medical_exam',
            'suggested_premium_loading',
            'condition_summary',
            'treatment_summary',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class CustomerFamilyMedicalHistoryCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CustomerFamilyMedicalHistory
        fields = [
            'customer',
            'condition_category',
            'condition_name',
            'condition_status',
            'family_relation',
            'age_diagnosed',
            'severity_level',
            'current_medication',
            'last_checkup_date',
            'doctor_name',
            'hospital_name',
            'insurance_impact',
            'premium_loading',
            'notes',
            'is_active',
        ]
    
    def validate(self, data):
        age_diagnosed = data.get('age_diagnosed')
        if age_diagnosed is not None and (age_diagnosed < 0 or age_diagnosed > 120):
            raise serializers.ValidationError(
                "Age diagnosed must be between 0 and 120 years."
            )
        
        premium_loading = data.get('premium_loading')
        if premium_loading is not None and (premium_loading < 0 or premium_loading > 100):
            raise serializers.ValidationError(
                "Premium loading must be between 0 and 100 percent."
            )
        
        return data


class CustomerFamilyMedicalHistoryUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CustomerFamilyMedicalHistory
        fields = [
            'condition_category',
            'condition_name',
            'condition_status',
            'family_relation',
            'age_diagnosed',
            'severity_level',
            'current_medication',
            'last_checkup_date',
            'doctor_name',
            'hospital_name',
            'insurance_impact',
            'premium_loading',
            'notes',
            'is_active',
        ]
    
    def validate(self, data):
       
        age_diagnosed = data.get('age_diagnosed', self.instance.age_diagnosed if self.instance else None)
        if age_diagnosed is not None and (age_diagnosed < 0 or age_diagnosed > 120):
            raise serializers.ValidationError(
                "Age diagnosed must be between 0 and 120 years."
            )
        
        premium_loading = data.get('premium_loading', self.instance.premium_loading if self.instance else None)
        if premium_loading is not None and (premium_loading < 0 or premium_loading > 100):
            raise serializers.ValidationError(
                "Premium loading must be between 0 and 100 percent."
            )
        
        return data


class CustomerFamilyMedicalHistoryListSerializer(serializers.ModelSerializer):
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    risk_score = serializers.IntegerField(read_only=True)
    is_high_risk = serializers.BooleanField(read_only=True)
    condition_summary = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerFamilyMedicalHistory
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'condition_category',
            'condition_name',
            'condition_status',
            'family_relation',
            'age_diagnosed',
            'severity_level',
            'insurance_impact',
            'premium_loading',
            'is_active',
            'risk_score',
            'is_high_risk',
            'condition_summary',
            'last_checkup_date',
            'created_at',
        ]


class CustomerFamilyMedicalHistoryRiskAssessmentSerializer(serializers.ModelSerializer):
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    risk_score = serializers.IntegerField(read_only=True)
    is_high_risk = serializers.BooleanField(read_only=True)
    requires_medical_exam = serializers.BooleanField(read_only=True)
    suggested_premium_loading = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    condition_summary = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerFamilyMedicalHistory
        fields = [
            'id',
            'customer_name',
            'customer_code',
            'condition_category',
            'condition_name',
            'family_relation',
            'severity_level',
            'insurance_impact',
            'premium_loading',
            'risk_score',
            'is_high_risk',
            'requires_medical_exam',
            'suggested_premium_loading',
            'condition_summary',
            'is_active',
            'created_at',
        ]


class CustomerFamilyMedicalHistorySummarySerializer(serializers.ModelSerializer):
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    condition_summary = serializers.CharField(read_only=True)
    treatment_summary = serializers.CharField(read_only=True)
    risk_score = serializers.IntegerField(read_only=True)
    is_high_risk = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CustomerFamilyMedicalHistory
        fields = [
            'id',
            'customer_name',
            'customer_code',
            'condition_category',
            'condition_name',
            'family_relation',
            'severity_level',
            'insurance_impact',
            'condition_summary',
            'treatment_summary',
            'risk_score',
            'is_high_risk',
            'is_active',
            'created_at',
        ]
