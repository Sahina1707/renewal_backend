
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('renewals', '0012_alter_renewalcase_status'),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE renewal_cases 
            SET status = CASE 
                WHEN status = 'completed' THEN 'renewed'
                WHEN status = 'cancelled' THEN 'failed'
                WHEN status = 'expired' THEN 'failed'
                WHEN status = 'due' THEN 'pending'
                WHEN status = 'overdue' THEN 'pending'
                WHEN status = 'not_required' THEN 'pending'
                ELSE status
            END
            WHERE status NOT IN (
                'uploaded', 'assigned', 'in_progress', 'pending', 'failed', 
                'renewed', 'not_interested', 'dnc_email', 'dnc_whatsapp', 
                'dnc_sms', 'dnc_call', 'dnc_bot_calling', 'payment_failed', 
                'customer_postponed'
            );
            """,
            reverse_sql="-- No reverse operation needed"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE renewal_cases DROP CONSTRAINT IF EXISTS renewal_cases_status_check;",
            reverse_sql="-- No reverse operation needed"
        ),
        
        migrations.RunSQL(
            """
            ALTER TABLE renewal_cases ADD CONSTRAINT renewal_cases_status_check 
            CHECK (status IN (
                'uploaded', 'assigned', 'in_progress', 'pending', 'failed', 
                'renewed', 'not_interested', 'dnc_email', 'dnc_whatsapp', 
                'dnc_sms', 'dnc_call', 'dnc_bot_calling', 'payment_failed', 
                'customer_postponed'
            ));
            """,
            reverse_sql="ALTER TABLE renewal_cases DROP CONSTRAINT renewal_cases_status_check;"
        ),
    ]
