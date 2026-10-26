import taggit.managers
from django.db import migrations, models

import utilities.json


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('dcim', '0250_cooling_infrastructure'),
        ('extras', '0144_customfield_status'),
        ('ipam', '0097_merge_ipaddress_host_index_and_multi_protocol_services'),
    ]

    operations = [
        migrations.CreateModel(
            name='SuggestionRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(
                    blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder,
                )),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='name')),
                ('priority', models.PositiveIntegerField(
                    default=100, verbose_name='priority',
                    help_text='Rules are tried from the lowest priority up. The first one that matches is used.',
                )),
                ('enabled', models.BooleanField(default=True, verbose_name='enabled')),
                ('interface_name', models.CharField(
                    default='mgmt0', max_length=64, verbose_name='interface name',
                    help_text=(
                        'Where the address goes when no interface is in a VLAN: this interface, else the '
                        "management-only interface, else the device's only interface. Created when there is none "
                        'of those.'
                    ),
                )),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='description')),
                ('roles', models.ManyToManyField(
                    blank=True, related_name='+', to='dcim.devicerole', verbose_name='roles',
                    help_text='Devices and VMs with one of these roles. Empty: any role.',
                )),
                ('device_types', models.ManyToManyField(
                    blank=True, related_name='+', to='dcim.devicetype', verbose_name='device types',
                    help_text='Devices of one of these types. Empty: any type. A rule with types never matches a VM.',
                )),
                ('vlans', models.ManyToManyField(
                    blank=True, related_name='+', to='ipam.vlan', verbose_name='VLANs',
                    help_text=(
                        'Addresses come only from these VLANs. When no interface is in one, the VLAN available at '
                        "the device's site is used. Empty: the VLAN of the device's interfaces."
                    ),
                )),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'suggestion rule',
                'verbose_name_plural': 'suggestion rules',
                'ordering': ('priority', 'name'),
            },
        ),
    ]
