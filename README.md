# netbox-nextip

A NetBox plugin for giving a device or virtual machine its management IP
address in one click.

Admins write **IP rules** that say, for a kind of device in a part of the
network, which VLAN the address comes from, what the new interface is called
and how the address is picked. A device page with no primary IPv4 then has a
*Next IP* card with the address its rule gives and an **Add IP** button. One click creates the
interface, puts it in the VLAN, creates the next free address on it and makes
that the primary IP.

## What it does

- **Rules per device type and place.** *Plugins → IP Rules*. A rule is for
  devices (optionally only some device types) or for virtual machines
  (optionally only some clusters), narrowed by region, site group, site and
  location. Every rule needs a region, a VLAN from a VLAN group that has a
  scope, or (VM rules) clusters, so no rule applies everywhere by accident.
- **One fixed VLAN per rule.** A device only matches a rule when NetBox lets
  it use that VLAN (the VLAN's site, or its VLAN group's scope).
- **The narrowest rule wins.** Rules are tried by priority, lowest first.
  With equal priority, a rule for a location beats one for a site, a site
  beats a site group, a site group beats a region, and a child region beats
  its parent.
- **The right interface.** A device with exactly one interface gets the
  address on that interface, unless that interface is in another VLAN or is
  a trunk port. Otherwise a new interface is created, named
  from a template such as `Vlan{vid}` or `oob{n}` (`{n}`: the lowest free
  number from 0), with the rule's interface type and management-only flag.
  Either way the interface gets the rule's VLAN as its untagged VLAN.
- **The address the rule asks for.** From the IP ranges inside the VLAN's
  prefix, or from the prefix when it has no range. By default the next
  address after the last used one, leaving gaps alone; a rule can count
  downwards from the end instead and can fill gaps. Status, role, DNS name
  template and whether it becomes the primary IP are set per rule.
- **No rule? Pick it.** When no rule matches, *Add IP…* opens a popup:
  pick the site and role (only when a VM has none), then narrow down by
  location (the device's own or one above it) and VLAN group and pick the
  VLAN. Each list only offers what fits
  the choices above it, and the popup shows the address and interface Add IP
  will create before you confirm.
- **Or type the address.** The popup also takes an address of your own.
  Type it alone and the VLAN and VLAN group follow from the prefix that
  holds it, or pick the VLAN first. The address must be in a prefix of that
  VLAN, free, and not the network, gateway or broadcast address. With a
  rule, *Other IP…* on the card opens the same popup.
- **A button next to Add Components.** While none of a device's interfaces
  has an IP address, *Add IP address* sits in the page's button bar and does
  the same as the card's button.
- **Says where it came from.** The change log entries of the interface, the
  address and the device say which rule (or popup choice) they came from.
- **Free means not in NetBox.** An address is free when no IP address object
  exists for it. DHCP pools (ranges marked *populated*) are never used.
- **IPv4 only.**

## Which address

1. The VLAN's prefixes: active IPv4 prefixes assigned to the rule's VLAN.
2. The active IP ranges inside those prefixes, not marked populated. The
   first range with a free address gives it. When every range is full, there
   is no address (the prefix is not used then).
3. No range: the prefix gives it, leaving out the rule's *skip first* /
   *skip last* addresses and every range in the prefix.

The first two addresses of a prefix (network and gateway) and the last
(broadcast) are never handed out, also not from a range that covers them.
A smaller prefix inside the VLAN's prefix is skipped: it belongs to another
VLAN, or it is used on its own with its own mask.
/31 and /32 prefixes are used in full.

Within a range or prefix:

| Order | Fill gaps off | Fill gaps on |
| --- | --- | --- |
| Upwards (default) | right after the highest used address | the lowest free address |
| Downwards | right below the lowest used address | the highest free address |

The mask is the prefix's.

## Requirements

- NetBox **4.7** (tested with 4.7.0).
- No other plugins.

## Installation

Install it into NetBox's Python environment:

```bash
pip install git+https://github.com/mattivaisanen/netbox-nextip.git
```

Add it to `configuration.py`:

```python
PLUGINS = [
    'netbox_nextip',
]
```

Run `python manage.py migrate netbox_nextip` and restart NetBox. There are no
`PLUGINS_CONFIG` settings; everything is set per rule. See
[docs/rules.md](docs/rules.md).

## REST API

`/api/plugins/nextip/rules/`: the IP rules (list, create, change, delete),
like any NetBox object.

## License

Apache 2.0, see [LICENSE](LICENSE).
