from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_provider', '0021_remove_zombie_waba_account_id'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE "whatsapp_messages" ADD COLUMN "provider_id" bigint NULL;
            ALTER TABLE "whatsapp_messages" ADD CONSTRAINT "whatsapp_messages_provider_id_fk_whatsapp_provider_id" FOREIGN KEY ("provider_id") REFERENCES "whatsapp_provider" ("id") DEFERRABLE INITIALLY DEFERRED;
            CREATE INDEX "whatsapp_messages_provider_id_idx" ON "whatsapp_messages" ("provider_id");
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS "whatsapp_messages_provider_id_idx";
            ALTER TABLE "whatsapp_messages" DROP CONSTRAINT IF EXISTS "whatsapp_messages_provider_id_fk_whatsapp_provider_id";
            ALTER TABLE "whatsapp_messages" DROP COLUMN IF EXISTS "provider_id";
            """
        ),
    ]