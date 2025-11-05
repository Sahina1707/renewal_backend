# Generated manually to add missing policy_number column

from django.db import migrations, connection


def add_policy_number_column_if_missing(apps, schema_editor):
    """Add policy_number column if it doesn't exist"""
    with connection.cursor() as cursor:
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'claims' AND column_name = 'policy_number'
        """)
        column_exists = cursor.fetchone()
        
        if not column_exists:
            # Add the column
            cursor.execute("""
                ALTER TABLE claims 
                ADD COLUMN policy_number VARCHAR(100) DEFAULT '';
            """)
            # Add index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS claims_policy_number_idx 
                ON claims(policy_number);
            """)


def remove_policy_number_column(apps, schema_editor):
    """Remove policy_number column (reverse operation)"""
    with connection.cursor() as cursor:
        # Drop index first
        cursor.execute("""
            DROP INDEX IF EXISTS claims_policy_number_idx;
        """)
        # Drop column
        cursor.execute("""
            ALTER TABLE claims DROP COLUMN IF EXISTS policy_number;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('claims', '0002_alter_claim_status'),
    ]

    operations = [
        migrations.RunPython(
            add_policy_number_column_if_missing,
            reverse_code=remove_policy_number_column
        ),
    ]

