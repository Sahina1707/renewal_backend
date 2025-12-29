from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix the role foreign key constraint to point to the correct table'

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                # Drop the existing foreign key constraint if it exists
                self.stdout.write('Dropping existing foreign key constraint...')
                cursor.execute("""
                    ALTER TABLE users_user 
                    DROP CONSTRAINT IF EXISTS users_user_role_id_854f2687_fk_users_role_id
                """)
                
                # Add the new foreign key constraint pointing to the 'user_role' table
                self.stdout.write('Adding new foreign key constraint...')
                cursor.execute("""
                    ALTER TABLE users_user 
                    ADD CONSTRAINT users_user_role_id_fk_user_role_id 
                    FOREIGN KEY (role_id) REFERENCES user_role(id) 
                    ON DELETE SET NULL
                """)
                
                self.stdout.write(
                    self.style.SUCCESS('Successfully fixed role foreign key constraint!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )