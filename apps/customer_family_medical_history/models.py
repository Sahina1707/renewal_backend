from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from apps.customers.models import Customer


class CustomerFamilyMedicalHistory(BaseModel):
    
    CONDITION_CATEGORY_CHOICES = [
        ('cardiovascular', 'Cardiovascular Disease'),
        ('diabetes', 'Diabetes'),
        ('cancer', 'Cancer'),
        ('respiratory', 'Respiratory Disease'),
        ('neurological', 'Neurological Disorder'),
        ('genetic', 'Genetic Disorder'),
        ('mental_health', 'Mental Health'),
        ('autoimmune', 'Autoimmune Disease'),
        ('kidney', 'Kidney Disease'),
        ('liver', 'Liver Disease'),
        ('blood', 'Blood Disorder'),
        ('bone', 'Bone/Joint Disease'),
        ('eye', 'Eye Disease'),
        ('ear', 'Ear Disease'),
        ('skin', 'Skin Disease'),
        ('other', 'Other'),
    ]
    
    CONDITION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('controlled', 'Controlled'),
        ('remission', 'In Remission'),
        ('cured', 'Cured'),
        ('chronic', 'Chronic'),
        ('acute', 'Acute'),
        ('terminal', 'Terminal'),
        ('unknown', 'Unknown'),
    ]
    
    FAMILY_RELATION_CHOICES = [
        ('self', 'Self'),
        ('spouse', 'Spouse'),
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('grandfather_paternal', 'Grandfather (Paternal)'),
        ('grandmother_paternal', 'Grandmother (Paternal)'),
        ('grandfather_maternal', 'Grandfather (Maternal)'),
        ('grandmother_maternal', 'Grandmother (Maternal)'),
        ('uncle_paternal', 'Uncle (Paternal)'),
        ('aunt_paternal', 'Aunt (Paternal)'),
        ('uncle_maternal', 'Uncle (Maternal)'),
        ('aunt_maternal', 'Aunt (Maternal)'),
        ('cousin', 'Cousin'),
        ('other', 'Other'),
    ]
    
    SEVERITY_LEVEL_CHOICES = [
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
        ('critical', 'Critical'),
        ('unknown', 'Unknown'),
    ]
    
    INSURANCE_IMPACT_CHOICES = [
        ('none', 'No Impact'),
        ('low', 'Low Impact'),
        ('medium', 'Medium Impact'),
        ('high', 'High Impact'),
        ('exclusion', 'Exclusion Required'),
        ('decline', 'Decline Coverage'),
    ]
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='family_medical_history',
        help_text="Customer this medical history belongs to"
    )
    
    condition_category = models.CharField(
        max_length=100,
        choices=CONDITION_CATEGORY_CHOICES,
        help_text="Category of medical condition"
    )
    
    condition_name = models.CharField(
        max_length=100,
        help_text="Specific name of the medical condition"
    )
    
    condition_status = models.CharField(
        max_length=100,
        choices=CONDITION_STATUS_CHOICES,
        help_text="Current status of the condition"
    )
    
    family_relation = models.CharField(
        max_length=50,
        choices=FAMILY_RELATION_CHOICES,
        help_text="Relationship to the customer"
    )
    
    age_diagnosed = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(120)],
        blank=True,
        null=True,
        help_text="Age when condition was diagnosed"
    )
    
    severity_level = models.CharField(
        max_length=100,
        choices=SEVERITY_LEVEL_CHOICES,
        default='unknown',
        help_text="Severity level of the condition"
    )
    
    current_medication = models.TextField(
        blank=True,
        help_text="Current medications for this condition"
    )
    
    last_checkup_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of last medical checkup for this condition"
    )
    
    doctor_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of treating doctor"
    )
    
    hospital_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Name of hospital or clinic"
    )
    
    insurance_impact = models.CharField(
        max_length=50,
        choices=INSURANCE_IMPACT_CHOICES,
        default='none',
        help_text="Impact on insurance coverage"
    )
    
    premium_loading = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Premium loading percentage due to this condition"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the condition"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this medical condition is currently active"
    )
    
    class Meta:
        db_table = 'customer_family_medical_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['condition_category']),
            models.Index(fields=['condition_status']),
            models.Index(fields=['family_relation']),
            models.Index(fields=['severity_level']),
            models.Index(fields=['insurance_impact']),
            models.Index(fields=['is_active']),
            models.Index(fields=['last_checkup_date']),
        ]
    
    def __str__(self):
        return f"{self.customer.full_name} - {self.family_relation} - {self.condition_name}"
    
    @property
    def risk_score(self):
        severity_scores = {
            'mild': 1,
            'moderate': 2,
            'severe': 3,
            'critical': 4,
            'unknown': 2
        }
        
        relation_scores = {
            'self': 4,
            'spouse': 2,
            'father': 3,
            'mother': 3,
            'brother': 2,
            'sister': 2,
            'son': 2,
            'daughter': 2,
            'grandfather_paternal': 1,
            'grandmother_paternal': 1,
            'grandfather_maternal': 1,
            'grandmother_maternal': 1,
            'uncle_paternal': 1,
            'aunt_paternal': 1,
            'uncle_maternal': 1,
            'aunt_maternal': 1,
            'cousin': 1,
            'other': 1
        }
        
        severity_score = severity_scores.get(self.severity_level, 2)
        relation_score = relation_scores.get(self.family_relation, 1)
        
        return severity_score * relation_score
    
    @property
    def is_high_risk(self):
        high_risk_conditions = [
            'cardiovascular', 'diabetes', 'cancer', 'neurological', 'genetic'
        ]
        high_risk_relations = ['self', 'father', 'mother']
        high_risk_severity = ['severe', 'critical']
        
        return (
            self.condition_category in high_risk_conditions or
            self.family_relation in high_risk_relations or
            self.severity_level in high_risk_severity or
            self.risk_score >= 8
        )
    
    @property
    def requires_medical_exam(self):
        exam_required_conditions = [
            'cardiovascular', 'diabetes', 'cancer', 'neurological'
        ]
        exam_required_severity = ['severe', 'critical']
        
        return (
            self.condition_category in exam_required_conditions or
            self.severity_level in exam_required_severity or
            self.family_relation == 'self'
        )
    
    @property
    def suggested_premium_loading(self):
        if self.premium_loading:
            return self.premium_loading
        
        risk_score = self.risk_score
        
        if risk_score <= 2:
            return 0.0
        elif risk_score <= 4:
            return 5.0
        elif risk_score <= 6:
            return 10.0
        elif risk_score <= 8:
            return 15.0
        else:
            return 25.0
    
    @property
    def condition_summary(self):
        parts = []
        parts.append(f"{self.get_family_relation_display()}")
        parts.append(f"{self.condition_name}")
        parts.append(f"({self.get_severity_level_display()})")
        if self.age_diagnosed:
            parts.append(f"Age: {self.age_diagnosed}")
        return " - ".join(parts)
    
    @property
    def treatment_summary(self):
        parts = []
        if self.doctor_name:
            parts.append(f"Dr. {self.doctor_name}")
        if self.hospital_name:
            parts.append(f"at {self.hospital_name}")
        if self.current_medication:
            parts.append(f"Medication: {self.current_medication[:50]}...")
        if self.last_checkup_date:
            parts.append(f"Last checkup: {self.last_checkup_date}")
        return " | ".join(parts) if parts else "No treatment information"
