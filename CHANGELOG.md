# Changelog

## 0.3.0 (2026-11-01)

The plugin is rebuilt around IP rules. Rules and settings of earlier
releases are removed: `manage.py migrate netbox_nextip` drops the old rule
table, and the `PLUGINS_CONFIG` settings are no longer read.

New:

- *IP Rules* (under Plugins): for devices of some device types, or VMs of
  some clusters, in a region, site group, site or location, which VLAN the
  address comes from, the name of the new interface, and how the address is
  picked. The narrowest matching rule wins at equal priority.
- *Add IP* on device and VM pages with no primary IPv4: uses the device's
  only interface, or creates the interface named by the rule (template with `{vid}`, `{vlan}`, `{n}`), puts
  it in the rule's VLAN, creates the address and makes it the primary IP.
- When no rule matches, *Add IP…* opens a popup: site and role (when a VM
  has none), location, VLAN group and VLAN, each narrowing the next, with a
  preview of the address and interface before you confirm. Location starts
  at the device's own. The VLAN group is picked when one group is the
  narrowest fit (location, then site, site group, region); the VLAN is only
  picked when the picked site of a VM makes a rule match.
- A *Next IP* card on device and VM pages shows the rule, VLAN, address and
  interface.
- The popup takes an address you type. Typed alone, the VLAN and VLAN group
  follow from the prefix that holds it. It is refused when it is not in a
  prefix of the VLAN, already in use, or the network, gateway or broadcast
  address. *Other IP…* on the card opens the popup also when a rule matches.
- *Add IP address* in the device and VM button bar, next to *Add Components*,
  while no interface has an IP address.
- Change log entries say which rule (or popup choice) an address came from.
- Per rule: count upwards after the last used address or downwards before
  the first one, fill gaps or not, addresses to skip at either end of a
  prefix, status, role and DNS name of the new address, and whether it
  becomes primary.
- The network address, gateway (the address after it) and broadcast address
  of a prefix are never handed out.
- `/api/plugins/nextip/rules/` for the rules.

Fixed (since the first 0.3.0 builds):

- Clicking *Add IP* twice, or two users at once, no longer adds two
  addresses.
- The popup's location only offers the device's own location and the ones
  above it, so it can no longer hand out a VLAN of another location.
- A device's only interface is not used when it is a trunk port, so its
  native VLAN is never changed.
- The popup preview shows the same rule and interface that *Add IP* uses.
- The popup only lists sites, roles, locations, VLAN groups and VLANs the
  user may view; the card hides the VLAN and prefix from users who may not.
- Interface names with padding such as `oob{n:02}` count up instead of
  reusing one name. Templates with very wide padding, positional fields or
  attribute lookups are rejected.
- A rule whose location is not in its site is rejected.
- An address taken at the same moment outside NetBox now shows a message
  instead of an error page.
- The device page works out the next IP once instead of twice.
- A smaller prefix inside the VLAN's prefix (for example one of another
  VLAN) is no longer handed out from the bigger prefix with the wrong mask.
- DNS names with an empty field, such as `{site}` on a VM without a site,
  no longer make Add IP fail: the empty label is dropped. A device name
  with nothing usable for DNS gives no DNS name instead of the bare domain.
- An IP range inside a smaller prefix of another VLAN no longer makes the
  VLAN's prefix look full.
- DNS name templates are checked for text a DNS name can't have (spaces),
  and both templates reject `!r` conversions and fields inside a padding.
- A rule whose last device type or cluster is deleted is disabled instead of
  quietly matching every type or cluster.
- A rule that lost its scope later (its VLAN group lost its scope) matches
  nothing instead of everything, and its page says so.
- A rule scoped only through its VLAN group (for example to one location)
  now wins ties against broader rules.
- Rules saved with a template the newer checks reject show the problem on
  the card instead of making a broken name.
- A disabled interface or a LAG member is never used as the only interface.
- The card's VLAN and prefix rows follow object permissions, not only model
  permissions.
- The popup only offers sites a VM's cluster (or host device) allows.
- The API can set a rule's device types and clusters (a list of IDs);
  before, it answered with a server error.
- The rule form only shows clusters for VM rules, and device types,
  location, interface type and management only for device rules.
- A popup opened from an old page, after the object got a primary IPv4,
  says so and offers nothing to add.
- When making the address primary waits for approval (another plugin holds
  the change), *Add IP* says so instead of reporting plain success.
- With netbox-change-approval, one *Add IP* is one approval request
  (interface, address and primary IP together) instead of three.
- *Add IP* no longer resets the device's or VM's interface count when it
  creates an interface (it also made an approved Add IP fail with a conflict).

Removed:

- The next-IP API for interfaces, the VLAN page panel, IPv6, cabled switch
  port VLANs and all `PLUGINS_CONFIG` settings.

## 0.2.0 (2026-10-26)

Suggestion rules and a one-click Assign on device pages.

## 0.1.0 (2026-10-24)

A *Next free IP* panel on interfaces.
