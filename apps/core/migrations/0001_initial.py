# Generated by Django 4.2.7 on 2025-07-31 12:00

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='APIRateLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('identifier', models.CharField(db_index=True, max_length=255)),
                ('endpoint', models.CharField(db_index=True, max_length=255)),
                ('request_count', models.PositiveIntegerField(default=1)),
                ('window_start', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_blocked', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('action', models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('login', 'Login'), ('logout', 'Logout'), ('view', 'View'), ('export', 'Export'), ('import', 'Import'), ('send', 'Send'), ('approve', 'Approve'), ('reject', 'Reject')], db_index=True, max_length=20)),
                ('model_name', models.CharField(db_index=True, max_length=100)),
                ('object_id', models.CharField(blank=True, db_index=True, max_length=100, null=True)),
                ('object_repr', models.TextField(blank=True, null=True)),
                ('changes', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('session_key', models.CharField(blank=True, max_length=40, null=True)),
                ('additional_data', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SystemConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('key', models.CharField(db_index=True, max_length=100, unique=True)),
                ('value', models.JSONField()),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('category', models.CharField(db_index=True, max_length=50)),
            ],
            options={
                'ordering': ['category', 'key'],
            },
        ),
    ]
