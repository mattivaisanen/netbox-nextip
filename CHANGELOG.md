# Changelog

## 0.2.0 (2026-10-26)

The plugin now works per device instead of per interface.

New:

- The top of a device or VM page shows the IP address it should get, with
  an *Assign* button. One click creates the address, puts it on the right
  interface and makes it the primary IP. It shows until the device has a
  primary IP. Setting `device_panel`.
- *IP Suggestion Rules* (under Plugins): admins choose which device roles
  and device types get a suggestion, from which VLANs, and on which
  interface. Devices no rule matches get none. Needs
  `manage.py migrate`.
- A rule's VLANs can be the management VLAN of every site: each device
  uses the one available at its site.
- When a device or VM has no suitable interface (for example a VM with no
  interfaces), *Assign* creates the one named in the rule.
- `/api/plugins/nextip/rules/` for the rules.

- An interface with no VLAN, such as a server NIC, gets its suggestion from
  the VLAN of the switch port it is cabled to, also through patch panels.
  Setting `cable_peer_vlans`.
- The API answer has `via`: the cabled interface whose VLAN it is.
- A DNS name for new addresses from a template, such as
  `{device}-{interface}.example.com`. Setting `dns_name`.
- Addresses created through the API can become the device's or VM's
  primary IP when it has none yet. Setting `primary_ip`.
- *Next free IP* panel on VLAN pages, with an *Add* button. Setting
  `vlan_panel`.

Removed:

- The *Next free IP* panel on interfaces and the `interface_panel`
  setting. The device page replaces it. The interface API stays.

Fixed:

- An address from the prefix is never inside a range. Before, only
  populated ranges were skipped, so a reserved range or a DHCP pool left
  out by `range_roles` could be handed out.
- `dns_name` keeps the dots of a device named as an FQDN and turns `_`
  into `-`. A template with an unknown field stops NetBox at startup
  instead of breaking every interface page.

## 0.1.0 (2026-10-24)

New:

- *Next free IP* panel on device and VM interfaces: the next free address
  from the interface's VLAN, and an *Assign* button that opens NetBox's IP
  address form with the address and the interface filled in.
- The address comes from an IP range inside the VLAN's prefix, or from the
  prefix itself when the VLAN has no range. Addresses without an IP address
  object are free. DHCP pools (ranges marked populated) are skipped.
- Settings for the order (first or last free address), addresses to keep
  free at either end of a prefix, range roles and statuses, prefix
  statuses, IPv4 and IPv6, tagged VLANs, and the interface's VRF.
- REST API: `GET /api/plugins/nextip/next-ip/?interface=<id>` suggests,
  `POST` creates the address and assigns it to the interface.
