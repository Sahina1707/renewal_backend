# Generated manually for adding channel_id field to Customer model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0004_add_verification_fields'),
        ('business_channels', '0009_channel_customer_channel_channel_custome_2776ba_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='channel_id',
            field=models.ForeignKey(
                blank=True,
                db_column='channel_id',
                help_text='Channel associated with this customer',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='customers',
                to='business_channels.channel'
            ),
        ),
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(fields=['channel_id'], name='customers_cu_channel_123abc_idx'),
        ),
    ]

