# Generated by Django 4.2.7 on 2025-07-31 12:00

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('customer_code', models.CharField(db_index=True, help_text='Auto-generated customer code like CUS2025001', max_length=20, unique=True)),
                ('customer_type', models.CharField(choices=[('individual', 'Individual'), ('corporate', 'Corporate'), ('sme', 'Small & Medium Enterprise'), ('government', 'Government')], default='individual', max_length=20)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(blank=True, max_length=100)),
                ('company_name', models.CharField(blank=True, max_length=200)),
                ('title', models.CharField(blank=True, max_length=50)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], max_length=10)),
                ('email', models.EmailField(db_index=True, max_length=254, validators=[django.core.validators.EmailValidator()])),
                ('phone', models.CharField(db_index=True, max_length=20, validators=[django.core.validators.RegexValidator('^\\+?1?\\d{9,15}$', 'Enter a valid phone number.')])),
                ('alternate_phone', models.CharField(blank=True, max_length=20, validators=[django.core.validators.RegexValidator('^\\+?1?\\d{9,15}$', 'Enter a valid phone number.')])),
                ('address_line1', models.CharField(blank=True, max_length=255)),
                ('address_line2', models.CharField(blank=True, max_length=255)),
                ('city', models.CharField(blank=True, db_index=True, max_length=100)),
                ('state', models.CharField(blank=True, db_index=True, max_length=100)),
                ('postal_code', models.CharField(blank=True, db_index=True, max_length=20)),
                ('country', models.CharField(db_index=True, default='India', max_length=100)),
                ('industry', models.CharField(blank=True, db_index=True, max_length=100)),
                ('business_registration_number', models.CharField(blank=True, max_length=50)),
                ('tax_id', models.CharField(blank=True, max_length=50)),
                ('annual_revenue', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('employee_count', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('suspended', 'Suspended'), ('prospect', 'Prospect'), ('dormant', 'Dormant')], db_index=True, default='active', max_length=20)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('vip', 'VIP')], db_index=True, default='medium', max_length=10)),
                ('profile', models.CharField(choices=[('Normal', 'Normal'), ('HNI', 'HNI (High Net-Worth Individual)')], db_index=True, default='Normal', help_text='Customer profile based on policy count', max_length=10)),
                ('preferred_contact_method', models.CharField(choices=[('email', 'Email'), ('phone', 'Phone'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp')], default='email', max_length=20)),
                ('preferred_language', models.CharField(default='en', max_length=10)),
                ('timezone', models.CharField(default='Asia/Kolkata', max_length=50)),
                ('communication_preferences', models.CharField(blank=True, help_text='Communication preferences from Excel', max_length=50)),
                ('email_notifications', models.BooleanField(default=True)),
                ('sms_notifications', models.BooleanField(default=True)),
                ('whatsapp_notifications', models.BooleanField(default=False)),
                ('marketing_communications', models.BooleanField(default=True)),
                ('kyc_status', models.CharField(choices=[('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected'), ('expired', 'Expired')], default='pending', help_text='KYC verification status from Excel', max_length=20)),
                ('kyc_documents', models.CharField(blank=True, help_text='KYC documents list from Excel', max_length=200)),
                ('credit_score', models.PositiveIntegerField(blank=True, null=True)),
                ('payment_terms', models.CharField(blank=True, max_length=50)),
                ('credit_limit', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('first_policy_date', models.DateField(blank=True, null=True)),
                ('last_policy_date', models.DateField(blank=True, null=True)),
                ('last_contact_date', models.DateTimeField(blank=True, null=True)),
                ('next_followup_date', models.DateTimeField(blank=True, null=True)),
                ('total_policies', models.PositiveIntegerField(default=0)),
                ('total_premium', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('lifetime_value', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('internal_notes', models.TextField(blank=True)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('custom_fields', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CustomerContact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(blank=True, max_length=100)),
                ('relationship', models.CharField(choices=[('spouse', 'Spouse'), ('child', 'Child'), ('parent', 'Parent'), ('sibling', 'Sibling'), ('employee', 'Employee'), ('partner', 'Business Partner'), ('authorized_person', 'Authorized Person'), ('other', 'Other')], max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=20, validators=[django.core.validators.RegexValidator('^\\+?1?\\d{9,15}$', 'Enter a valid phone number.')])),
                ('is_primary', models.BooleanField(default=False)),
                ('is_emergency_contact', models.BooleanField(default=False)),
                ('can_make_changes', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-is_primary', 'first_name'],
            },
        ),
        migrations.CreateModel(
            name='CustomerDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('document_type', models.CharField(choices=[('id_proof', 'ID Proof'), ('address_proof', 'Address Proof'), ('income_proof', 'Income Proof'), ('business_registration', 'Business Registration'), ('tax_document', 'Tax Document'), ('bank_statement', 'Bank Statement'), ('medical_report', 'Medical Report'), ('photo', 'Photograph'), ('signature', 'Signature'), ('authorization', 'Authorization Letter'), ('other', 'Other')], db_index=True, max_length=30)),
                ('document_number', models.CharField(blank=True, max_length=100)),
                ('is_verified', models.BooleanField(default=False)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('verification_notes', models.TextField(blank=True)),
                ('issue_date', models.DateField(blank=True, null=True)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('issuing_authority', models.CharField(blank=True, max_length=200)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CustomerInteraction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('interaction_type', models.CharField(choices=[('call', 'Phone Call'), ('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('meeting', 'Meeting'), ('visit', 'Site Visit'), ('complaint', 'Complaint'), ('inquiry', 'Inquiry'), ('claim', 'Claim'), ('renewal', 'Renewal'), ('other', 'Other')], db_index=True, max_length=20)),
                ('direction', models.CharField(choices=[('inbound', 'Inbound'), ('outbound', 'Outbound')], max_length=10)),
                ('status', models.CharField(choices=[('completed', 'Completed'), ('scheduled', 'Scheduled'), ('cancelled', 'Cancelled'), ('no_response', 'No Response')], default='completed', max_length=20)),
                ('subject', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('outcome', models.TextField(blank=True)),
                ('scheduled_at', models.DateTimeField(blank=True, null=True)),
                ('duration_minutes', models.PositiveIntegerField(blank=True, null=True)),
                ('requires_followup', models.BooleanField(default=False)),
                ('followup_date', models.DateTimeField(blank=True, null=True)),
                ('followup_notes', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CustomerNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField()),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], default='medium', max_length=10)),
                ('is_private', models.BooleanField(default=False, help_text='Only visible to creator')),
                ('tags', models.JSONField(blank=True, default=list)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CustomerSegment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('criteria', models.JSONField(default=dict, help_text='Segmentation criteria in JSON format')),
                ('color', models.CharField(default='#007bff', help_text='Hex color code', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
    ]
