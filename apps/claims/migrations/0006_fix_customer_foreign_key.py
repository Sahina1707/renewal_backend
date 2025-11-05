# Generated manually to fix customer foreign key constraint

from django.db import migrations, connection


def fix_customer_foreign_key(apps, schema_editor):
    """Fix the customer foreign key to point to customers_customer table"""
    with connection.cursor() as cursor:
        # Get all foreign key constraints on customer_id column
        cursor.execute("""
            SELECT 
                tc.constraint_name,
                kcu.table_name,
                ccu.table_name AS foreign_table_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'claims'
                AND kcu.column_name = 'customer_id'
                AND tc.table_schema = 'public';
        """)
        
        results = cursor.fetchall()
        
        # Drop all existing foreign key constraints on customer_id
        for result in results:
            constraint_name, table_name, foreign_table_name = result
            # Drop the existing constraint
            cursor.execute(f"""
                ALTER TABLE claims 
                DROP CONSTRAINT IF EXISTS {constraint_name} CASCADE;
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


def reverse_fix_customer_foreign_key(apps, schema_editor):
    """Reverse operation - restore original constraint if needed"""
    with connection.cursor() as cursor:
        # Drop the constraint we created
        cursor.execute("""
            ALTER TABLE claims 
            DROP CONSTRAINT IF EXISTS claims_customer_id_fkey;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('claims', '0005_add_reported_date_field'),
    ]

    operations = [
        migrations.RunPython(
            fix_customer_foreign_key,
            reverse_code=reverse_fix_customer_foreign_key
        ),
    ]

