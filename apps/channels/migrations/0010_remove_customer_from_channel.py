# Generated manually for removing customer field from Channel model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0005_add_channel_id_to_customer'),
        ('business_channels', '0009_channel_customer_channel_channel_custome_2776ba_idx'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='channel',
            name='channel_custome_2776ba_idx',
        ),
        migrations.RemoveField(
            model_name='channel',
            name='customer',
        ),
    ]

