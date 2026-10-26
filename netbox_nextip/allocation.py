"""
Which address an interface gets next.

The VLANs of an interface (its untagged VLAN, and its tagged VLANs when the
tagged_vlans setting is on) each give one suggestion per address family. An
interface with no VLAN of its own uses the VLANs of the interface at the
other end of its cable (a server NIC takes the switch port's VLAN), with the
cable_peer_vlans setting:

1. The VLAN's prefixes: prefixes whose VLAN it is, with an allowed status
   (and in the interface's VRF, with match_interface_vrf).
2. The ranges inside those prefixes, with an allowed status and role. Ranges
   marked populated (DHCP pools) never count.
3. The first (or last) address of the first range that has one free. When
   there is no range, the same from the prefix itself, skipping the network
   and broadcast addresses, the configured addresses at either end and every
   range in the prefix (one that does not count, such as a reserved range or
   a DHCP pool of another role, is still not free to hand out).

An address is free when no IP address object exists for it in the VRF.
Nothing here writes.
"""
from dataclasses import dataclass

import netaddr

from ipam.models import IPRange, Prefix, VLAN

from .settings import get_setting

FIRST, LAST = 'first', 'last'

# Why a suggestion has no address.
NO_PREFIX = 'no-prefix'  # the VLAN has no prefix of this family
NO_RANGE = 'no-range'    # the VLAN has no range, and prefix_fallback is off
FULL = 'full'            # every range (or the prefix) is in use


@dataclass
class Suggestion:
    vlan: VLAN
    family: int
    address: str | None = None      # with the prefix's mask: '10.0.0.5/24'
    prefix: Prefix | None = None    # the VLAN prefix the address is in
    range: IPRange | None = None    # the range it came from, None when from the prefix
    via: object = None              # the cabled interface whose VLAN it is, None when the interface's own
    problem: str | None = None      # NO_PREFIX, NO_RANGE or FULL when there is no address

    @property
    def vrf(self):
        return self.prefix.vrf if self.prefix else None

    @property
    def tenant(self):
        source = self.range or self.prefix
        return source.tenant if source else None


def interface_vlans(interface):
    """The VLANs an interface takes addresses from, untagged first."""
    vlans = [interface.untagged_vlan] if interface.untagged_vlan_id else []
    if get_setting('tagged_vlans') and interface.pk:
        vlans += [vlan for vlan in interface.tagged_vlans.order_by('vid') if vlan.pk != interface.untagged_vlan_id]
    return vlans


def vlan_source(interface):
    """
    (VLANs, via): the interface's own VLANs, or when it has none, those of
    the interface at the other end of its cable (through patch panels), which
    is then via. A VM interface or one cabled to anything but one interface
    has only its own.
    """
    vlans = interface_vlans(interface)
    if vlans or not get_setting('cable_peer_vlans'):
        return vlans, None
    peers = getattr(interface, 'connected_endpoints', None) or []
    if len(peers) == 1 and isinstance(peers[0], type(interface)):
        if peer_vlans := interface_vlans(peers[0]):
            return peer_vlans, peers[0]
    return [], None


def suggest(interface, family=None, vlans=None):
    """
    One Suggestion per VLAN of the interface and address family. family
    and vlans (VLAN pk's) narrow it down; by default every family in the
    families setting and every VLAN. An empty list means the interface has
    no VLAN (of those).
    """
    families = [family] if family else get_setting('families')
    source, via = vlan_source(interface)
    source = [vlan for vlan in source if vlans is None or vlan.pk in vlans]
    vrf = interface.vrf if interface.vrf_id and get_setting('match_interface_vrf') else None
    suggestions = [suggest_for_vlan(v, f, vrf) for v in source for f in families]
    for suggestion in suggestions:
        suggestion.via = via
    return suggestions


def first_free(suggestions):
    """The first suggestion of each family that has an address."""
    found = {}
    for suggestion in suggestions:
        if suggestion.address and suggestion.family not in found:
            found[suggestion.family] = suggestion
    return list(found.values())


def suggest_for_vlan(vlan, family, vrf=None):
    result = Suggestion(vlan=vlan, family=family)
    prefixes = vlan_prefixes(vlan, family, vrf)
    if not prefixes:
        result.problem = NO_PREFIX
        return result
    order = get_setting('order')

    ranges = [(prefix, iprange) for prefix in prefixes for iprange in prefix_ranges(prefix)]
    if ranges:
        if found := _first_found(ranges, order, range_address):
            return found_in(result, *found)
        if not get_setting('prefix_fallback_when_full'):
            result.problem = FULL
            return result
    elif not get_setting('prefix_fallback'):
        result.problem = NO_RANGE
        return result

    if found := _first_found([(prefix, None) for prefix in prefixes], order, prefix_address):
        return found_in(result, *found)
    result.problem = FULL
    return result


def _first_found(pools, order, pick):
    """(prefix, range, address) of the first pool with a free address, in order."""
    for prefix, iprange in (reversed(pools) if order == LAST else pools):
        address = pick(iprange or prefix, order)
        if address is not None:
            return prefix, iprange, address
    return None


def found_in(result, prefix, iprange, address):
    result.prefix, result.range = prefix, iprange
    result.address = f'{address}/{prefix.prefix.prefixlen}'
    return result


def vlan_prefixes(vlan, family, vrf=None):
    prefixes = Prefix.objects.filter(vlan=vlan, status__in=get_setting('prefix_statuses'))
    if vrf is not None:
        prefixes = prefixes.filter(vrf=vrf)
    return [prefix for prefix in prefixes.select_related('vrf', 'tenant') if prefix.family == family]


def prefix_ranges(prefix):
    """The ranges in a prefix that count as the VLAN's, in address order."""
    ranges = prefix.get_child_ranges(status__in=get_setting('range_statuses'), mark_populated=False)
    if roles := get_setting('range_roles'):
        ranges = ranges.filter(role__slug__in=roles)
    return list(ranges.select_related('tenant').order_by('start_address'))


def range_address(iprange, order):
    """The free address of a range (netaddr.IPAddress), or None."""
    first, last = int(iprange.start_address.ip), int(iprange.end_address.ip)
    taken = _taken(iprange.get_child_ips(), first, last)
    return _as_address(free_number(first, last, taken, order), iprange.family)


def prefix_address(prefix, order):
    """The free address of a prefix (netaddr.IPAddress), or None."""
    first, last = usable_bounds(prefix)
    first += get_setting('prefix_skip_first')
    last -= get_setting('prefix_skip_last')
    taken = _taken(prefix.get_child_ips(), first, last)
    for iprange in prefix.get_child_ranges():
        taken.append((int(iprange.start_address.ip), int(iprange.end_address.ip)))
    return _as_address(free_number(first, last, taken, order), prefix.family)


def usable_bounds(prefix):
    """
    First and last usable address of a prefix, as numbers. Like NetBox:
    IPv4 leaves out the network and broadcast addresses, IPv6 the
    subnet-router anycast address; pools, IPv4 /31-/32 and IPv6
    /127-/128 are usable in full.
    """
    network = prefix.prefix
    first, last = network.first, network.last
    if prefix.is_pool or network.prefixlen >= (31 if network.version == 4 else 127):
        return first, last
    if network.version == 4:
        return first + 1, last - 1
    return first + 1, last


def _taken(ip_addresses, first, last):
    """Existing addresses between first and last, as (n, n) intervals."""
    numbers = (int(address.ip) for address in ip_addresses.values_list('address', flat=True))
    return [(n, n) for n in numbers if first <= n <= last]


def _as_address(number, family):
    return None if number is None else netaddr.IPAddress(number, version=family)


def free_number(first, last, taken, order=FIRST):
    """
    The lowest (FIRST) or highest (LAST) number from first to last that is
    in none of the taken (start, end) intervals, or None. Intervals may
    overlap and stick out of the bounds.
    """
    if order == LAST:
        candidate = last
        for start, end in sorted(taken, key=lambda interval: interval[1], reverse=True):
            if end < candidate:
                break
            candidate = min(candidate, start - 1)
        return candidate if candidate >= first else None
    candidate = first
    for start, end in sorted(taken):
        if start > candidate:
            break
        candidate = max(candidate, end + 1)
    return candidate if candidate <= last else None
