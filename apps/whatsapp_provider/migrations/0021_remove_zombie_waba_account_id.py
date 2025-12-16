from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_provider', '0020_remove_legacy_credentials'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE whatsapp_phone_numbers DROP COLUMN IF EXISTS waba_account_id;",
            reverse_sql="ALTER TABLE whatsapp_phone_numbers ADD COLUMN waba_account_id varchar(100);"
        ),
    ]