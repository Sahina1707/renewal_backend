# Generated manually for removing channel_id field from RenewalCase model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('renewals', '0012_remove_priority_column'),
        ('business_channels', '0010_remove_customer_from_channel'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='renewalcase',
            name='renewal_cas_channel_f4e671_idx',
        ),
        migrations.RemoveField(
            model_name='renewalcase',
            name='channel_id',
        ),
    ]

