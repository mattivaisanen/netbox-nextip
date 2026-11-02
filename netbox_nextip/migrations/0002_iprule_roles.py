from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0250_cooling_infrastructure'),
        ('netbox_nextip', '0001_ip_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='iprule',
            name='roles',
            field=models.ManyToManyField(blank=True, related_name='+', to='dcim.devicerole'),
        ),
    ]
