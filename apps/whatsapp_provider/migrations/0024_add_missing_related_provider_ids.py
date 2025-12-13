from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_provider', '0023_add_missing_webhook_provider_id'),
    ]

    operations = [
        # 1. Fix whatsapp_flows
        migrations.RunSQL(
            sql="""
            ALTER TABLE "whatsapp_flows" ADD COLUMN "provider_id" bigint NULL;
            ALTER TABLE "whatsapp_flows" ADD CONSTRAINT "whatsapp_flows_provider_id_fk_whatsapp_provider_id" FOREIGN KEY ("provider_id") REFERENCES "whatsapp_provider" ("id") DEFERRABLE INITIALLY DEFERRED;
            CREATE INDEX "whatsapp_flows_provider_id_idx" ON "whatsapp_flows" ("provider_id");
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS "whatsapp_flows_provider_id_idx";
            ALTER TABLE "whatsapp_flows" DROP CONSTRAINT IF EXISTS "whatsapp_flows_provider_id_fk_whatsapp_provider_id";
            ALTER TABLE "whatsapp_flows" DROP COLUMN IF EXISTS "provider_id";
            """
        ),
        # 2. Fix whatsapp_account_health_logs
        migrations.RunSQL(
            sql="""
            ALTER TABLE "whatsapp_account_health_logs" ADD COLUMN "provider_id" bigint NULL;
            ALTER TABLE "whatsapp_account_health_logs" ADD CONSTRAINT "whatsapp_account_health_logs_provider_id_fk_whatsapp_provider_id" FOREIGN KEY ("provider_id") REFERENCES "whatsapp_provider" ("id") DEFERRABLE INITIALLY DEFERRED;
            CREATE INDEX "whatsapp_account_health_logs_provider_id_idx" ON "whatsapp_account_health_logs" ("provider_id");
            """,
            reverse_sql="ALTER TABLE \"whatsapp_account_health_logs\" DROP COLUMN IF EXISTS \"provider_id\";"
        ),
        # 3. Fix whatsapp_account_usage_logs
        migrations.RunSQL(
            sql="""
            ALTER TABLE "whatsapp_account_usage_logs" ADD COLUMN "provider_id" bigint NULL;
            ALTER TABLE "whatsapp_account_usage_logs" ADD CONSTRAINT "whatsapp_account_usage_logs_provider_id_fk_whatsapp_provider_id" FOREIGN KEY ("provider_id") REFERENCES "whatsapp_provider" ("id") DEFERRABLE INITIALLY DEFERRED;
            CREATE INDEX "whatsapp_account_usage_logs_provider_id_idx" ON "whatsapp_account_usage_logs" ("provider_id");
            """,
            reverse_sql="ALTER TABLE \"whatsapp_account_usage_logs\" DROP COLUMN IF EXISTS \"provider_id\";"
        ),
    ]