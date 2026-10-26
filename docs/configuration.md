# Configuration

Which devices and VMs get a suggestion, and from which VLANs, is set in
NetBox itself: *Plugins → IP Suggestion Rules* (see the README). The
settings below are the rest. They go in NetBox's `configuration.py`. Every
key is optional; these are the defaults:

```python
PLUGINS_CONFIG = {
    'netbox_nextip': {
        'device_panel': True,
        'vlan_panel': True,
        'families': [4],
        'tagged_vlans': False,
        'cable_peer_vlans': True,
        'match_interface_vrf': True,
        'order': 'first',
        'prefix_statuses': ['active'],
        'range_statuses': ['active'],
        'range_roles': [],
        'prefix_fallback': True,
        'prefix_fallback_when_full': False,
        'prefix_skip_first': 0,
        'prefix_skip_last': 0,
        'ip_status': 'active',
        'dns_name': '',
        'primary_ip': False,
    },
}
```

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `device_panel` | bool | `True` | Show the suggested IP and the *Assign* button at the top of device and VM pages. The REST API works either way. |
| `vlan_panel` | bool | `True` | Show the *Next free IP* panel on VLAN pages: the next address per family (ignoring any interface VRF), with an *Add* button for the IP address form. |
| `families` | list | `[4]` | Address families to suggest: `[4]`, `[6]` or `[4, 6]`. With both, a device gets one address per family it has no primary IP of, and *Assign* creates both. |
| `tagged_vlans` | bool | `False` | Also suggest from the tagged VLANs of a trunk port, one line per VLAN. The untagged (access or native) VLAN always counts. |
| `cable_peer_vlans` | bool | `True` | When an interface has no VLAN, use the VLANs of the interface at the other end of its cable (through patch panels). A server NIC takes the switch port's VLAN. Only device interfaces have cables. |
| `match_interface_vrf` | bool | `True` | When the interface has a VRF, only use the VLAN's prefixes in that VRF. |
| `order` | str | `'first'` | `'first'`: the lowest free address. `'last'`: the highest. With several ranges or prefixes, `'last'` also starts from the last one. |
| `prefix_statuses` | list | `['active']` | Prefix statuses that count as the VLAN's prefix. |
| `range_statuses` | list | `['active']` | IP range statuses that count as the VLAN's range. |
| `range_roles` | list | `[]` | Role slugs, such as `['static']`. When set, only ranges with one of these roles count; other ranges are ignored (their addresses can still be suggested from the prefix). Empty: ranges of any role count. |
| `prefix_fallback` | bool | `True` | When the VLAN's prefix has no range, suggest from the prefix itself. `False`: no suggestion without a range. |
| `prefix_fallback_when_full` | bool | `False` | When every range is full, suggest from the prefix. `False`: the panel says *No free addresses*. |
| `prefix_skip_first` | int | `0` | Addresses at the start of a prefix that are never suggested, after the network address. `1` keeps `.1` free for the gateway. Ranges are not affected. |
| `prefix_skip_last` | int | `0` | The same at the end of a prefix, before the broadcast address. |
| `dns_name` | str | `''` | DNS name of a new address, as a template: `{device}`, `{interface}` (`Gi1/0/1` becomes `gi1-0-1`), `{vlan}` (name), `{vid}` and `{site}` (slug). For example `'{device}-{interface}.example.com'`. Used by *Assign*, and by the API when the request has no `dns_name`. Empty: no DNS name. |
| `primary_ip` | bool | `False` | API only: make an address created by `POST` the primary IPv4 or IPv6 of its device or VM, when it has none of that family yet. Never replaces an existing primary IP. *Assign* on the device page always makes it primary. |
| `ip_status` | str | `'active'` | Status of the IP address that *Assign* and the API create. |

Ranges marked *populated* (DHCP pools) are never used. An address from the
prefix is never inside any range, whatever its status, role or populated
mark.

## Permissions

| Permission | Allows |
| --- | --- |
| `ipam.add_ipaddress` and change on the device or VM | The *Assign* button (and `POST` to the API, which needs only the first). Object permissions apply to the new address and the device like anywhere in NetBox. Creating an interface also needs permission to add interfaces. |
| `netbox_nextip.*_suggestionrule` | Seeing and editing suggestion rules. |
| `view` on the device or interface | Seeing the suggestion and `GET` from the API. |
