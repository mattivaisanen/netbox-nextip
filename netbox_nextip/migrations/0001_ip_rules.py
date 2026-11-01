import django.db.models.deletion
import taggit.managers
from django.db import migrations, models

import utilities.json

# Tables of the rule model in releases before 0.3.0. Their data is not carried over.
OLD_TABLES = (
    'netbox_nextip_suggestionrule_roles',
    'netbox_nextip_suggestionrule_device_types',
    'netbox_nextip_suggestionrule_vlans',
    'netbox_nextip_suggestionrule',
)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('dcim', '0250_cooling_infrastructure'),
        ('extras', '0144_customfield_status'),
        ('ipam', '0097_merge_ipaddress_host_index_and_multi_protocol_services'),
        ('virtualization', '0060_consolidate_unique_constraints'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f'DROP TABLE IF EXISTS {table} CASCADE' for table in OLD_TABLES],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='IPRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(
                    blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder,
                )),
                ('name', models.CharField(max_length=100, unique=True)),
                ('priority', models.PositiveIntegerField(default=100)),
                ('enabled', models.BooleanField(default=True)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('object_type', models.CharField(default='device', max_length=20)),
                ('interface_name', models.CharField(default='Vlan{vid}', max_length=64)),
                ('interface_type', models.CharField(default='virtual', max_length=50)),
                ('mgmt_only', models.BooleanField(default=False)),
                ('order', models.CharField(default='after-last', max_length=20)),
                ('fill_gaps', models.BooleanField(default=False)),
                ('skip_first', models.PositiveSmallIntegerField(default=0)),
                ('skip_last', models.PositiveSmallIntegerField(default=0)),
                ('ip_status', models.CharField(default='active', max_length=50)),
                ('ip_role', models.CharField(blank=True, max_length=50)),
                ('dns_name', models.CharField(blank=True, max_length=255)),
                ('make_primary', models.BooleanField(default=True)),
                ('region', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                    to='dcim.region',
                )),
                ('site_group', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                    to='dcim.sitegroup',
                )),
                ('site', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                    to='dcim.site',
                )),
                ('location', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                    to='dcim.location',
                )),
                ('vlan', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name='+', to='ipam.vlan',
                )),
                ('device_types', models.ManyToManyField(blank=True, related_name='+', to='dcim.devicetype')),
                ('clusters', models.ManyToManyField(blank=True, related_name='+', to='virtualization.cluster')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'IP rule',
                'verbose_name_plural': 'IP rules',
                'ordering': ('priority', 'name'),
            },
        ),
    ]
