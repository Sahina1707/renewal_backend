from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_provider', '0022_add_missing_provider_id'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE "whatsapp_webhook_events" ADD COLUMN "provider_id" bigint NULL;
            ALTER TABLE "whatsapp_webhook_events" ADD CONSTRAINT "whatsapp_webhook_events_provider_id_fk_whatsapp_provider_id" FOREIGN KEY ("provider_id") REFERENCES "whatsapp_provider" ("id") DEFERRABLE INITIALLY DEFERRED;
            CREATE INDEX "whatsapp_webhook_events_provider_id_idx" ON "whatsapp_webhook_events" ("provider_id");
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS "whatsapp_webhook_events_provider_id_idx";
            ALTER TABLE "whatsapp_webhook_events" DROP CONSTRAINT IF EXISTS "whatsapp_webhook_events_provider_id_fk_whatsapp_provider_id";
            ALTER TABLE "whatsapp_webhook_events" DROP COLUMN IF EXISTS "provider_id";
            """
        ),
    ]