# netbox-nextip

A NetBox plugin that tells you which IP address a device or VM should get,
and assigns it in one click. Open a device and the top of the page says
*Suggested IP `10.20.5.23/24` on mgmt0 · VLAN Mgmt*, with an *Assign*
button. Assign creates the address, puts it on the interface (creating the
interface when there is none) and makes it the primary IP.

## What it does

- **Admins decide who gets a suggestion.** *Plugins → IP Suggestion
  Rules*: each rule names device roles, device types and VLANs (empty means
  any), and the interface the address goes on. Rules are tried by priority;
  the first that matches is used. A device no rule matches gets nothing.
- **One suggestion per device.** Shown until the device has a primary IP.
  It comes from an interface that is in one of the rule's VLANs (its own
  VLAN, or the switch port it is cabled to). When no interface is, it
  comes from the rule's VLAN available at the device's site, so one rule
  can list the management VLAN of every site.
- **One-click Assign.** The address goes on the interface named in the
  rule, else the management-only interface, else the device's only
  interface. With none of those (a VM with no interfaces, an odd box made
  from a generic device type), the named interface is created. The address
  becomes the primary IP. If someone took it in the meantime, the next free
  one is used and the message says so.
- **Free means not in NetBox.** An address is free when no IP address
  object exists for it in the VRF, whatever its status. Pending addresses
  of netbox-change-approval exist as objects, so they count as taken.
- **Ranges first, then the prefix.** The address comes from an IP range
  inside the VLAN's prefix; with no range, from the prefix itself. DHCP
  pools (ranges marked *populated*) are never used.
- **Shows it on the VLAN too.** A VLAN's page has a *Next free IP* panel
  per family, with an *Add* button.
- **Configurable:** IPv4, IPv6 or both; tagged VLANs of trunk ports;
  addresses to keep free at the start or end of a prefix (for gateways);
  which range roles and statuses count; DNS name template. See
  [docs/configuration.md](docs/configuration.md).

## Which address

For each VLAN (an interface's untagged one, and the tagged ones with
`tagged_vlans`; with no VLAN, those of the interface it is cabled to; or
the rule's VLAN) and each address family:

1. The VLAN's prefixes: prefixes assigned to the VLAN with an allowed
   status. When the interface has a VRF, only prefixes in that VRF.
2. The ranges inside those prefixes, in the same VRF, with an allowed
   status and role, not marked populated. The first range with a free
   address gives it.
3. No range: the prefix gives it, leaving out the network and broadcast
   addresses (IPv6: the subnet-router anycast address), the addresses set
   by `prefix_skip_first` and `prefix_skip_last`, and every range in the
   prefix (also reserved ones, or ones of a role that does not count).
4. Ranges, but all full: *No free addresses* (or the prefix, with
   `prefix_fallback_when_full`).

The mask of the suggestion is the prefix's.

## Requirements

- NetBox **4.7** (tested with 4.7.0). NetBox refuses to load the plugin on
  older versions.
- No other plugins. Works with
  [netbox-change-approval](https://github.com/mattivaisanen/netbox-change-approval):
  addresses created with *Assign* or the API are gated like any other.

## Installation

Install it into NetBox's own Python environment (on a standard install,
`source /opt/netbox/venv/bin/activate` first):

```bash
pip install git+https://github.com/mattivaisanen/netbox-nextip.git
```

Add it to `configuration.py`:

```python
PLUGINS = [
    'netbox_nextip',
]
```

run `python manage.py migrate netbox_nextip` and restart NetBox. Settings are in
[docs/configuration.md](docs/configuration.md).

With netbox-docker, install it from a local checkout in your plugin image:

```dockerfile
COPY netbox-nextip /opt/netbox-nextip
RUN uv pip install --no-cache /opt/netbox-nextip
```

## REST API

- `GET /api/plugins/nextip/next-ip/?interface=<id>` (or `vminterface=<id>`):
  one entry per VLAN and family, with `address`, `vlan`, `vrf`, `prefix`,
  `range` (null when the address is from the prefix), `via` (the cabled
  interface whose VLAN it is, or null) and `problem`
  (`no-prefix`, `no-range` or `full` when there is no address). `vlan=<id>`
  and `family=4|6` narrow it down. Reserves nothing.
- `POST /api/plugins/nextip/next-ip/` with `{"interface": <id>}`: creates
  the next free address and assigns it to the interface. `vlan` and
  `family` pick which one (default: the first that has a free address).
  Other keys (`description`, `dns_name`, `role`, `tenant`, `status`,
  `tags`, `custom_fields`) go to the new address. Two requests at the same
  time never get the same address. Answers 201 with the address, or 409
  when there is none. Needs permission to add IP addresses.

- `/api/plugins/nextip/rules/`: the suggestion rules (list, create,
  change, delete), like any NetBox object.

## License

Apache 2.0, see [LICENSE](LICENSE).
