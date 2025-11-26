from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    WhatsAppProvider, 
    WhatsAppPhoneNumber,
    WhatsAppMessage,
    WhatsAppMessageTemplate,
)


@receiver(pre_save, sender=WhatsAppProvider)
def whatsapp_provider_pre_save(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=WhatsAppProvider)
def whatsapp_provider_post_save(sender, instance, created, **kwargs):
    
    if created:
        print(f"Created new WhatsApp Provider: {instance.name} (Type: {instance.provider_type})")


@receiver(pre_save, sender=WhatsAppPhoneNumber)
def whatsapp_phone_number_pre_save(sender, instance, **kwargs):
    if not instance.provider:
        return
    
    if instance.is_active and not instance.pk:
        has_other_active_numbers = WhatsAppPhoneNumber.objects.filter(
            provider=instance.provider, is_active=True
        ).exists()
        if not has_other_active_numbers:
            instance.is_primary = True
    if instance.is_primary:
        WhatsAppPhoneNumber.objects.filter(
            provider=instance.provider
        ).exclude(pk=instance.pk).update(is_primary=False)


@receiver(post_save, sender=WhatsAppProvider)
def whatsapp_provider_post_save(sender, instance, created, **kwargs):
    
    if created:
        print(f"Created new WhatsApp Provider: {instance.name} (Type: {instance.provider_type})")
        
        if instance.phone_number_id:
            if not WhatsAppPhoneNumber.objects.filter(phone_number_id=instance.phone_number_id).exists():
                display_num = instance.phone_number_id
                
                WhatsAppPhoneNumber.objects.create(
                    provider=instance,  
                    phone_number_id=instance.phone_number_id,
                    phone_number=display_num, 
                    display_phone_number=display_num, 
                    status='verified', 
                    is_primary=True,
                    is_active=True
                )
                print(f" -> Auto-created Phone Number table entry for: {instance.phone_number_id}")

@receiver(post_save, sender=WhatsAppMessage)
def whatsapp_message_post_save(sender, instance, created, **kwargs):
    
    if created:
        direction = instance.get_direction_display()
        message_type = instance.get_message_type_display()
        print(f"Created {direction} {message_type} message: {instance.message_id}")

@receiver(post_save, sender=WhatsAppMessageTemplate)
def whatsapp_message_template_post_save(sender, instance, created, **kwargs):
    
    if created:
        print(f"Created message template: {instance.name} for Provider {instance.provider.name}")
        
    if instance.status == 'approved' and not instance.approved_at:
        instance.approved_at = timezone.now()
        instance.save(update_fields=['approved_at'])
    