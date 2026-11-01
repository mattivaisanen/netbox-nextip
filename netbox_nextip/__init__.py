"""
Add the next free IP address to a device or VM in one click.

Admins write IP rules (models.IPRule): which devices or VMs a rule is for
(device type or cluster, region, site, location, VLAN group), the VLAN the
address comes from, the name of the interface it goes on and how the
address is picked. A device page with no primary IPv4 shows the address
its rule gives, with an Add IP button. See DEVELOPER.md.
"""
from netbox.plugins import PluginConfig


class NextIPConfig(PluginConfig):
    name = 'netbox_nextip'
    verbose_name = 'Next IP'
    description = 'Add the next free IP address to a device or VM in one click, following admin rules.'
    version = '0.3.0'
    author = 'Matti'
    base_url = 'nextip'
    # The oldest NetBox release the tests run on.
    min_version = '4.7.0'

    # Everything is set per rule in the UI; there are no PLUGINS_CONFIG settings.
    default_settings = {}

    template_extensions = 'template_content.template_extensions'

    def ready(self):
        super().ready()
        from . import signals  # noqa: F401 (connects the receivers)


config = NextIPConfig
