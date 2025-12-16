from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_provider', '0019_whatsappprovider_api_version'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE whatsapp_provider DROP COLUMN IF EXISTS credentials;",
            reverse_sql="ALTER TABLE whatsapp_provider ADD COLUMN credentials text;"
        ),
    ]
