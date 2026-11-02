# IP rules

Every field of an IP rule, and what it does. Rules are edited under
*Plugins → IP Rules* or through `/api/plugins/nextip/rules/`.

## Rule

| Field | Meaning |
| --- | --- |
| Name | Unique name. |
| Priority | Rules are tried lowest first. Default 100. |
| Enabled | Disabled rules are ignored. |
| Description | Free text. |

## Applies to

| Field | Meaning |
| --- | --- |
| Applies to | *Devices* or *Virtual machines*. The form only shows the fields that kind of rule uses: clusters for VM rules; device types, location, interface type and management only for device rules. |
| Device types | Device rules: only these types. Empty: any. |
| Clusters | VM rules: only VMs in these clusters. Empty: any. |
| Roles | Only devices or VMs with one of these roles. Empty: any. VM rules only offer roles marked for virtual machines. |

## Scope

Every filled-in field must match. A rule needs at least a region, a VLAN
from a VLAN group that has a scope, or (VM rules) clusters.

| Field | Matches |
| --- | --- |
| Region | Devices at a site in this region or a region below it. |
| Site group | Devices at a site in this group or a group below it. |
| Site | Devices at this site. |
| Location | Devices in this location or one below it. Device rules only. With a site, it must be a location of that site. |

A VM's site is its own site field.

A rule that loses its scope later (its VLAN's group loses its scope, or the
VLAN leaves the group) matches nothing; the rule page says so. A rule whose
last device type, role or cluster is deleted is disabled, so it doesn't turn
into "any type". A region, site group, site or location a rule names can't be
deleted; edit or delete the rule first.

When several enabled rules match, the lowest priority wins. With equal
priority, the narrowest scope wins: location, then site, then site group,
then region (a deeper region or group before its parent), then a rule with
device types or clusters before one without, then a rule with roles before
one without. Then the name. A rule with none
of these place fields counts with the scope of its VLAN's group.

## Interface

| Field | Meaning |
| --- | --- |
| VLAN | The address comes from this VLAN, and it becomes the interface's untagged VLAN. A device that may not use the VLAN (by the VLAN's site or VLAN group scope) never matches. |
| Interface name | Template. Fields: `{vid}`, `{vlan}` (VLAN name) and `{n}`, with optional padding such as `{n:02}` (at most 64 wide). Default `Vlan{vid}`. |
| Interface type | Devices only. Default *Virtual*. |
| Management only | Devices only. Marks the new interface management-only. |

A device or VM with exactly one interface gets the address on that interface
instead, unless the interface is in another VLAN or is a trunk (mode
*Tagged*, *Tagged (All)* or *Q-in-Q*, with no untagged VLAN or another one);
the name template is not used then. A trunk's native VLAN is never changed.

With `{n}` in the name, `{n}` is the lowest number from 0 that gives a name
the device does not have yet, so every click makes a new interface. Without
it, an interface that already has the name is used when it has no untagged
VLAN or the rule's VLAN, and is not a trunk; one in another VLAN or a trunk
blocks the rule (the device page says so).

Examples: `Vlan{vid}` gives `Vlan210` for VLAN 210, `oob{n}` gives `oob0`,
then `oob1`.

## Address

| Field | Meaning |
| --- | --- |
| Order | *Upwards, after the last used address* (default) or *Downwards, before the first used address*. |
| Fill gaps | Also use free addresses between used ones. Then upwards takes the lowest free address and downwards the highest. |
| Skip first / Skip last | More addresses at the start and end of a prefix that are never handed out. Not used for IP ranges. |

The network address, the gateway (the address after it) and the broadcast
address of a prefix are never handed out, whatever the rule says. /31 and /32
prefixes are used in full.

## New IP address

| Field | Meaning |
| --- | --- |
| IP status | Status of the new address. Default *Active*. |
| IP role | Role of the new address. Default none. |
| DNS name | Template. Fields: `{device}`, `{interface}`, `{vid}`, `{vlan}`, `{site}` (slug). Each part is made a DNS label (`Gi1/0/1` becomes `gi1-0-1`); a device named as an FQDN keeps its dots; empty labels are dropped. Text between the fields: letters, digits, `.`, `-` and `_`. Empty: no DNS name. |
| Make primary | The new address becomes the device's or VM's primary IPv4. Default on. |

The address gets the VRF of its prefix and the tenant of its range (or
prefix).

## When the button shows

In the *Next IP* card on a device or VM page, when the device has no primary
IPv4 and an enabled rule matches it. Clicking it needs permission to add IP addresses and
interfaces and to change the device. With *Make primary* off, the button
stays and offers the next address after each click.

The *Add IP address* button next to *Add Components* does the same, and shows
while none of the device's interfaces has an IP address.

## When no rule matches

The *Next IP* card still shows (for users who may add IPs), and *Add IP…*
opens a popup. Every list only holds what the user may view:

1. **Role** and **Site**, only when a VM has none. They are saved on the VM.
2. **Location** (devices with a location): the device's own location and
   the ones above it; starts at its own. Choosing a higher one, or none,
   offers fewer VLANs. It is a filter only and is not saved.
3. **VLAN group**: the groups of the VLANs offered.
4. **VLAN**: the VLANs the device or VM may use at that site and location,
   in that group.

The popup never picks a VLAN for you, except for a VM whose picked site
makes a rule match: then that rule's VLAN (and its group) is picked, since
*Add IP* will use it anyway. The VLAN group is picked when it is the only
one offered, or the only one at the narrowest place that has any: the
location (deepest first), then the site, site group and region (deepest
first). With two or more groups there, you pick.

5. **IP address** (optional): empty means the next free address. A typed
   address with no VLAN picked sets the VLAN and VLAN group from the
   smallest active prefix that holds it; change the address and they follow
   again, pick a VLAN by hand and it stays. The address must be in an
   active prefix of the VLAN (not in a smaller prefix of another VLAN), have
   no IP address object, not be in a populated range, and not be the
   prefix's network, gateway or broadcast address. It is checked again when
   you add it; if it was taken in the meantime, nothing is added.

The same popup opens from *Other IP…* on the card when a rule matches. Its
VLAN starts at the rule's; left as it is, *Add IP* does what the rule says.
Another VLAN uses the default settings below instead of the rule's.

Every change reloads the popup, and its bottom part shows what *Add IP* will
do: the VLAN, the address, the prefix or range it comes from and the
interface. If a rule matches once site and role are set, that rule is used.
Otherwise every rule field is at its default: after the last used address,
on the only interface or a new `Vlan{vid}` interface, active, made primary.
