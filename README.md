# netbox-nextip

A NetBox plugin that gives a device or virtual machine its management IP
address in one click. Admins write IP rules that say, for a kind of device in
a part of the network, which VLAN the address comes from and what the new
interface is called. A device page with no primary IPv4 then shows the
address its rule gives, and *Add IP* creates the interface, puts it in the
VLAN, creates the next free address on it and makes it the primary IP.

## What it does

Everything below works the same for devices and virtual machines; "device"
stands for either.

- **Shows the next IP.** A *Next IP* card on the device page shows the rule,
  the VLAN, the address and the interface it goes on, while the device has
  no primary IPv4.
- **Adds it in one click.** *Add IP* creates the address on the right
  interface and makes it the primary IP. The same button sits next to *Add
  Components* while none of the device's interfaces has an IP address.
- **Uses or creates the interface.** A device with exactly one interface gets
  the address on it, unless that interface is in another VLAN or is a trunk.
  Otherwise a new interface is created from the rule's name template, with
  the rule's interface type and management-only flag. Either way the
  interface gets the rule's VLAN as its untagged VLAN.
- **Rules per device type, role and place.** A rule is for devices
  (optionally only some device types) or virtual machines (optionally only
  some clusters), optionally only some roles, narrowed by region, site
  group, site and location. The
  narrowest matching rule wins at equal priority.
- **Picks the address the rule asks for.** From the IP ranges inside the
  VLAN's prefix, or from the prefix when it has no range. Upwards after the
  last used address by default; a rule can count downwards and fill gaps.
- **Popup when no rule matches.** *Add IP…* lets you pick the location, VLAN
  group and VLAN, each list narrowing the next, and shows the address and
  interface before you confirm. *Other IP…* opens it also when a rule
  matches.
- **Takes a typed address.** In the popup you can type an address instead.
  Typed alone, the VLAN follows from the prefix that holds it. It is refused
  when it is in use, outside the VLAN's prefixes, or the network, gateway or
  broadcast address.
- **Says where an address came from.** The change log entries of the
  interface, the address and the device name the rule or popup choice.
- **Free means not in NetBox.** An address is free when no IP address object
  exists for it. Populated ranges (DHCP pools) are never used. IPv4 only.

## Requirements

- NetBox **4.7** (tested with 4.7.0). NetBox refuses to load the plugin on
  older versions.
- No other plugins. Works with
  [netbox-change-approval](https://github.com/mattivaisanen/netbox-change-approval)
  when it is installed.

## Installation

The plugin isn't on PyPI; install it from GitHub into NetBox's own Python
environment (on a standard install, `source /opt/netbox/venv/bin/activate`
first):

```bash
pip install git+https://github.com/mattivaisanen/netbox-nextip.git
```

Add it to `configuration.py`:

```python
PLUGINS = [
    'netbox_nextip',
]
```

Then, from your NetBox install:

```bash
python manage.py migrate netbox_nextip
```

and restart NetBox. There are no `PLUGINS_CONFIG` settings; everything is
set per rule.

With netbox-docker, add the plugin to `plugin_requirements.txt` (or install
it from a local checkout in your plugin image) and run the migration in the
netbox container.

## Upgrading

```bash
pip install --upgrade git+https://github.com/mattivaisanen/netbox-nextip.git
python manage.py migrate netbox_nextip
```

and restart NetBox. Upgrading from 0.2 removes the old rules and settings;
see [CHANGELOG.md](CHANGELOG.md).

## Rules

Under **Plugins → IP Rules**. Rules are tried by priority (lowest first).
With equal priority, a rule for a location beats one for a site, a site
beats a site group, and a site group beats a region. Every rule needs a
region, a VLAN from a VLAN group that has a scope, or (VM rules) clusters,
so no rule applies everywhere by accident. All fields are described in
[docs/rules.md](docs/rules.md).

| Field | Meaning |
| --- | --- |
| Applies to | Devices or virtual machines. |
| Device types, clusters | Optional. Only devices of these types, or VMs in these clusters. |
| Roles | Optional. Only devices or VMs with one of these roles. |
| Region, site group, site, location | Optional. Where the rule applies. Child regions, groups and locations match too. |
| VLAN | The VLAN the address comes from. A device that may not use the VLAN never matches. |
| Interface name | Template for a new interface: `{vid}`, `{vlan}` and `{n}` (lowest free number from 0). Default `Vlan{vid}`. |
| Interface type, management only | Devices only. Set on a new interface. |
| Order, fill gaps | Upwards or downwards from the used addresses, and whether gaps between them are used. |
| Skip first, skip last | Extra addresses at either end of a prefix that are never handed out. |
| IP status, IP role, DNS name | Set on the new address. The DNS name is a template. |
| Make primary | The new address becomes the primary IPv4. Default on. |

### Which address

1. The active IPv4 prefixes assigned to the rule's VLAN.
2. The active IP ranges inside those prefixes, not marked populated. The
   first range with a free address gives it. When every range is full there
   is no address.
3. No range: the prefix gives it, leaving out the skipped addresses and
   every range in the prefix.

The network, gateway (the address after it) and broadcast address of a
prefix are never handed out. /31 and /32 prefixes are used in full. The new
address gets the prefix's mask and VRF.

## REST API

`/api/plugins/nextip/rules/`: the IP rules (create, read, update, delete),
like any NetBox object.

## With netbox-change-approval

IP rules are ordinary NetBox objects, so changes to them need approval like
any other object. One *Add IP* is one change request: the interface, the
address and the primary IP are approved together. While making the address
primary waits for approval, *Add IP* says so.

## License

Apache License 2.0. See [LICENSE](LICENSE).
