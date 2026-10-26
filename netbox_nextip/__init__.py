"""
Suggest the IP address a device or VM should get, and assign it in one click.

Suggestion rules (SuggestionRule) pick which devices get one and from which
VLANs. The address comes from an IP range inside the VLAN's prefix when there
is one, otherwise from the prefix itself. An address is free when no IP
address object exists for it. See DEVELOPER.md.
"""
from netbox.plugins import PluginConfig


class NextIPConfig(PluginConfig):
    name = 'netbox_nextip'
    verbose_name = 'Next IP'
    description = 'Suggest the IP address of a device or VM and assign it in one click.'
    version = '0.2.0'
    author = 'Matti'
    base_url = 'nextip'
    # Only claim what CI tests (.github/workflows/test.yml).
    min_version = '4.7.0'

    # Every key is described in docs/configuration.md.
    default_settings = {
        # Show the suggested IP and the Assign button on device and VM pages.
        'device_panel': True,
        # Show the "Next free IP" panel on VLAN pages.
        'vlan_panel': True,
        # Address families to suggest: [4], [6] or [4, 6].
        'families': [4],
        # Also suggest from the tagged VLANs of a trunk port (the untagged
        # VLAN always counts).
        'tagged_vlans': False,
        # An interface with no VLAN uses the VLAN of the interface cabled
        # to it (a server NIC takes the switch port's VLAN).
        'cable_peer_vlans': True,
        # When the interface has a VRF, only use prefixes in that VRF.
        'match_interface_vrf': True,
        # 'first' or 'last' free address.
        'order': 'first',
        # Prefixes and ranges with these statuses count as the VLAN's.
        'prefix_statuses': ['active'],
        'range_statuses': ['active'],
        # Only ranges with one of these role slugs count. Empty: any role.
        'range_roles': [],
        # Use the VLAN's prefix when it has no range.
        'prefix_fallback': True,
        # Also use the prefix when the VLAN's ranges are all full.
        'prefix_fallback_when_full': False,
        # Addresses at the start and end of a prefix that are never
        # suggested (1 at the start keeps .1 for the gateway). Only for
        # prefixes; ranges are used as they are.
        'prefix_skip_first': 0,
        'prefix_skip_last': 0,
        # Status of the IP address that Assign and the API create.
        'ip_status': 'active',
        # DNS name of a new address, such as '{device}.example.com'. Fields:
        # {device}, {interface}, {vlan}, {vid}, {site}. Empty: none.
        'dns_name': '',
        # API only (Assign always does it): make a new address the device's
        # or VM's primary IP when it has none of that family.
        'primary_ip': False,
    }

    template_extensions = 'template_content.template_extensions'

    def ready(self):
        super().ready()
        from .new_address import check_dns_name
        check_dns_name()


config = NextIPConfig
