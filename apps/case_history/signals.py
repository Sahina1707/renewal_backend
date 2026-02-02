from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Case, CaseHistory, CaseComment

User = get_user_model()
@receiver(post_save, sender=Case)
def create_case_history_on_save(sender, instance, created, **kwargs):
    if created:
        pass
    else:
        pass

@receiver(post_save, sender=CaseComment)
def create_comment_history_on_save(sender, instance, created, **kwargs):
    if created:
        pass

@receiver(pre_save, sender=Case)
def track_case_changes(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Case.objects.get(pk=instance.pk)
            
            if old_instance.status != instance.status:
                pass
            
            if old_instance.handling_agent != instance.handling_agent:
                pass
                
        except Case.DoesNotExist:
            pass


def create_case_history_entry(case, action, description, user=None, **kwargs):
    CaseHistory.objects.create(
        case=case,
        action=action,
        description=description,
        created_by=user,
        **kwargs
    )


def create_validation_history(case, validation_result, user=None):
    if validation_result.get('is_valid', False):
        description = "Case validation passed - all required fields present and valid"
    else:
        errors = validation_result.get('errors', [])
        description = f"Case validation failed - {', '.join(errors)}"
    
    create_case_history_entry(
        case=case,
        action='validation',
        description=description,
        user=user,
        metadata={'validation_result': validation_result}
    )

def create_assignment_history(case, agent, user=None):
    if agent:
        description = f"Case assigned to agent {agent.get_full_name()}"
        new_value = str(agent.id)
    else:
        description = "Case unassigned from agent"
        new_value = ""
    
    create_case_history_entry(
        case=case,
        action='assignment',
        description=description,
        user=user,
        new_value=new_value
    )


def create_status_change_history(case, old_status, new_status, user=None):
    create_case_history_entry(
        case=case,
        action='status_changed',
        description=f"Status changed from {old_status} to {new_status}",
        user=user,
        old_value=old_status,
        new_value=new_status
    )


def create_comment_history(case, comment, action='comment_added', user=None):
    description = f"Comment {action.replace('_', ' ')}: {comment.comment[:100]}{'...' if len(comment.comment) > 100 else ''}"
    
    create_case_history_entry(
        case=case,
        action=action,
        description=description,
        user=user,
        related_comment=comment
    )