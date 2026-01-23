from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from apps.core.models import BaseModel
from apps.customer_assets.models import CustomerAssets

class CustomerVehicle(BaseModel):
    
    VEHICLE_TYPE_CHOICES = [
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('truck', 'Truck'),
        ('van', 'Van'),
        ('suv', 'SUV'),
        ('bus', 'Bus'),
        ('bicycle', 'Bicycle'),
        ('scooter', 'Scooter'),
        ('other', 'Other'),
    ]
    
    FUEL_TYPE_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
        ('cng', 'CNG'),
        ('lpg', 'LPG'),
        ('other', 'Other'),
    ]
    
    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('very_good', 'Very Good'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    customer_assets = models.ForeignKey(
        CustomerAssets,
        on_delete=models.CASCADE,
        related_name='vehicles',
        help_text="Customer assets this vehicle belongs to"
    )
    
    vehicle_name = models.CharField(
        max_length=100,
        help_text="Name/Brand of the vehicle"
    )
    
    model_year = models.IntegerField(
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(2030)
        ],
        help_text="Manufacturing year of the vehicle"
    )
    
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        default='car',
        help_text="Type of vehicle"
    )
    
    fuel_type = models.CharField(
        max_length=20,
        choices=FUEL_TYPE_CHOICES,
        blank=True,
        help_text="Fuel type of the vehicle"
    )
    
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        blank=True,
        help_text="Current condition of the vehicle"
    )
    
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current market value of the vehicle"
    )
    
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True,
        help_text="Original purchase price of the vehicle"
    )
    
    registration_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Vehicle registration number"
    )
    
    engine_capacity = models.CharField(
        max_length=20,
        blank=True,
        help_text="Engine capacity (e.g., 1.6L, 150cc)"
    )
    
    mileage = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Current mileage/odometer reading"
    )
    
    class Meta:
        db_table = 'customer_vehicles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer_assets']),
            models.Index(fields=['vehicle_type']),
            models.Index(fields=['model_year']),
            models.Index(fields=['fuel_type']),
            models.Index(fields=['condition']),
        ]
    
    def __str__(self):
        return f"{self.vehicle_name} ({self.model_year}) - {self.customer_assets.customer.full_name}"
    
    @property
    def vehicle_summary(self):
        """Return a summary of vehicle information"""
        parts = [self.vehicle_name]
        if self.model_year:
            parts.append(str(self.model_year))
        if self.vehicle_type:
            parts.append(self.get_vehicle_type_display())
        return " - ".join(parts)
    
    @property
    def depreciation_rate(self):
        """Calculate depreciation rate if purchase price is available"""
        if self.purchase_price and self.purchase_price > 0:
            depreciation = float(self.purchase_price) - float(self.value)
            return round((depreciation / float(self.purchase_price)) * 100, 2)
        return 0
    
    @property
    def vehicle_age(self):
        """Calculate vehicle age in years"""
        from datetime import datetime
        current_year = datetime.now().year
        return current_year - self.model_year
    
    @property
    def vehicle_score(self):
        """Calculate a vehicle score based on various factors"""
        score = 0
        
        type_scores = {
            'car': 8,
            'suv': 9,
            'motorcycle': 6,
            'truck': 7,
            'van': 7,
            'bus': 5,
            'bicycle': 3,
            'scooter': 4,
            'other': 5,
        }
        score += type_scores.get(self.vehicle_type, 5)
        
        # Score based on condition
        condition_scores = {
            'excellent': 10,
            'very_good': 8,
            'good': 6,
            'fair': 4,
            'poor': 2,
        }
        score += condition_scores.get(self.condition, 0)
        
        # Score based on age (newer vehicles get higher scores)
        age = self.vehicle_age
        if age <= 2:
            score += 10
        elif age <= 5:
            score += 8
        elif age <= 10:
            score += 6
        elif age <= 15:
            score += 4
        else:
            score += 2
        
        # Score based on value
        if self.value >= 1000000:  
            score += 10
        elif self.value >= 500000:  
            score += 8
        elif self.value >= 200000:  
            score += 6
        elif self.value >= 100000:  
            score += 4
        else:
            score += 2
        
        return min(score, 40)  
