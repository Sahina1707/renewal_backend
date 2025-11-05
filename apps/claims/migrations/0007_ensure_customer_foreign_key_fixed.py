# Generated manually to ensure customer foreign key points to customers_customer table

from django.db import migrations, connection


def ensure_customer_foreign_key_fixed(apps, schema_editor):
    """Ensure the customer foreign key points to customers_customer table"""
    with connection.cursor() as cursor:
        # Drop all existing foreign key constraints on customer_id
        cursor.execute("""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN (
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE constraint_type = 'FOREIGN KEY'
                        AND table_name = 'claims'
                        AND constraint_name IN (
                            SELECT tc.constraint_name
                            FROM information_schema.table_constraints AS tc
                            JOIN information_schema.key_column_usage AS kcu
                                ON tc.constraint_name = kcu.constraint_name
                                AND tc.table_schema = kcu.table_schema
                            WHERE tc.constraint_type = 'FOREIGN KEY'
                                AND tc.table_name = 'claims'
                                AND kcu.column_name = 'customer_id'
                                AND tc.table_schema = 'public'
                        )
                ) LOOP
                    EXECUTE 'ALTER TABLE claims DROP CONSTRAINT IF EXISTS ' || quote_ident(r.constraint_name) || ' CASCADE';
                END LOOP;
            END $$;
        """)
        
        # Check if customers_customer table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'customers_customer'
            );
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Recreate the constraint pointing to the correct table
            cursor.execute("""
                ALTER TABLE claims 
                ADD CONSTRAINT claims_customer_id_fkey 
                FOREIGN KEY (customer_id) 
                REFERENCES customers_customer(id) 
                ON DELETE CASCADE;
            """)


def reverse_ensure_customer_foreign_key_fixed(apps, schema_editor):
    """Reverse operation"""
    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE claims 
            DROP CONSTRAINT IF EXISTS claims_customer_id_fkey;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('claims', '0006_fix_customer_foreign_key'),
    ]

    operations = [
        migrations.RunPython(
            ensure_customer_foreign_key_fixed,
            reverse_code=reverse_ensure_customer_foreign_key_fixed
        ),
    ]

