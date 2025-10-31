from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("email_templates", "0003_remove_emailtemplate_category_id_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE email_templates
                ADD COLUMN IF NOT EXISTS category_id uuid;
            """,
            reverse_sql="""
                ALTER TABLE email_templates
                DROP COLUMN IF EXISTS category_id;
            """,
        ),
    ]

