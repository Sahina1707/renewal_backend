from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
import pytz 

User = get_user_model()

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='general_settings')
    dark_mode = models.BooleanField(default=False)
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('te', 'Telugu'),
        ('ta', 'Tamil'),
        ('kn', 'Kannada'),
        ('bn', 'Bengali'),
        ('mr', 'Marathi'),
        ('gu', 'Gujarati'),
        ('ml', 'Malayalam'),
        ('ur', 'Urdu'),
        ('pa', 'Punjabi'),
        ('as', 'Assamese'),
        ('or','odia'),
        ('es', 'Español'),
        ('fr', 'Français'),
    ]
    TIMEZONE_CHOICES = [
        ('UTC-8', 'UTC-8'),
        ('UTC-5', 'UTC-5'),
        ('UTC+0', 'UTC+0'),
        ('UTC+1', 'UTC+1'),
        ('UTC+8', 'UTC+8'),
    ]
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.common_timezones]
    time_zone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='Asia/Kolkata')
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    mfa_enabled = models.BooleanField(default=False)
    class Meta:
        db_table = 'general_user_settings'
    def __str__(self):
        return f"Settings for {self.user.username}"

@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.create(user=instance)