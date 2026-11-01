"""
Which address a rule gives next. Reads only.

1. The VLAN's IPv4 prefixes: active prefixes assigned to the rule's VLAN.
2. The active IP ranges inside those prefixes, not marked populated (DHCP
   pools). With ranges, the address comes from the first range (last, when
   going downwards) that has one; when all are full there is none.
3. Without ranges, from the prefix itself, leaving out the rule's
   skip_first / skip_last addresses and every range in the prefix.

The first address of a prefix (network), the one after it (gateway) and
the last (broadcast) are never handed out, also not from a range that
covers them. /31 and /32 prefixes are used in full. A smaller prefix inside
a VLAN prefix is not used through the bigger one: it belongs to another VLAN,
or (same VLAN) it is used on its own, with its own mask.

An address is used when an IP address object exists for it, whatever its
status. Within a pool, the rule's order and fill_gaps decide which free
address is next (see free_number()).

An address typed in the Add IP popup is checked by check_address() instead:
it must be in a prefix of the VLAN, free, and not a reserved address.
"""
from dataclasses import dataclass

import netaddr
from django.utils.translation import gettext_lazy as _

from ipam.choices import IPRangeStatusChoices, PrefixStatusChoices
from ipam.models import IPAddress, IPRange, Prefix

from .choices import AddressOrderChoices

# Why there is no address.
NO_PREFIX = 'no-prefix'  # the VLAN has no active IPv4 prefix
FULL = 'full'            # no free address in the order the rule asks for

# Why a typed address can't be used (check_address()), in words for the user.
TYPED_PROBLEMS = {
    'bad-address': _('not an IPv4 address'),
    'not-in-vlan': _('the address is not in an active prefix of this VLAN'),
    'reserved': _("the address is the prefix's network, gateway or broadcast address"),
    'taken': _('the address is already in use'),
}


@dataclass
class Suggestion:
    address: str | None = None      # with the prefix's mask: '10.0.0.5/24'
    prefix: Prefix | None = None    # the VLAN prefix the address is in
    range: IPRange | None = None    # the range it came from, None when from the prefix
    problem: str | None = None      # NO_PREFIX or FULL when there is no address

    @property
    def vrf(self):
        return self.prefix.vrf if self.prefix else None

    @property
    def tenant(self):
        source = self.range or self.prefix
        return source.tenant if source else None


def suggest(rule):
    """The next address of the rule's VLAN, as a Suggestion."""
    prefixes = [
        prefix for prefix in Prefix.objects.filter(vlan=rule.vlan, status=PrefixStatusChoices.STATUS_ACTIVE)
        .select_related('vrf', 'tenant').order_by('prefix')
        if prefix.family == 4
    ]
    if not prefixes:
        return Suggestion(problem=NO_PREFIX)
    ranges = [(prefix, iprange) for prefix in prefixes for iprange in prefix_ranges(prefix)]
    pools = ranges or [(prefix, None) for prefix in prefixes]
    if rule.order == AddressOrderChoices.BEFORE_FIRST:
        pools.reverse()
    for prefix, iprange in pools:
        if iprange:
            number = range_number(iprange, prefix, rule)
        else:
            number = prefix_number(prefix, rule)
        if number is not None:
            address = netaddr.IPAddress(number, version=4)
            return Suggestion(address=f'{address}/{prefix.prefix.prefixlen}', prefix=prefix, range=iprange)
    return Suggestion(problem=FULL)


def prefix_ranges(prefix):
    """
    The active, not populated ranges in a prefix, in address order. A range
    inside a smaller prefix belongs to that one, not to this prefix.
    """
    ranges = prefix.get_child_ranges(status=IPRangeStatusChoices.STATUS_ACTIVE, mark_populated=False)
    children = child_prefixes(prefix)
    return [
        iprange for iprange in ranges.select_related('vrf', 'tenant').order_by('start_address')
        if not any(start <= int(iprange.start_address.ip) and int(iprange.end_address.ip) <= end
                   for start, end in children)
    ]


def range_number(iprange, prefix, rule):
    first, last = int(iprange.start_address.ip), int(iprange.end_address.ip)
    used = _used(iprange.get_child_ips(), first, last)
    taken = [(n, n) for n in used] + reserved(prefix) + child_prefixes(prefix)
    return free_number(first, last, taken, used, rule.order, rule.fill_gaps)


def prefix_number(prefix, rule):
    first, last = prefix.prefix.first, prefix.prefix.last
    if reserved(prefix):
        first, last = first + 2, last - 1  # after the network address and gateway, before broadcast
    first += rule.skip_first
    last -= rule.skip_last
    # Every range in the prefix is off limits, also reserved ones and DHCP pools, and so is every
    # smaller prefix inside it.
    blocks = [(int(r.start_address.ip), int(r.end_address.ip)) for r in prefix.get_child_ranges()]
    blocks += child_prefixes(prefix)
    # Addresses inside those do not move "the last used address" of the prefix.
    used = [
        n for n in _used(prefix.get_child_ips(), first, last)
        if not any(start <= n <= end for start, end in blocks)
    ]
    taken = [(n, n) for n in used] + blocks + reserved(prefix)
    return free_number(first, last, taken, used, rule.order, rule.fill_gaps)


def child_prefixes(prefix):
    """
    The parts of a prefix taken by smaller prefixes inside it, as (start, end)
    intervals. A child prefix of another VLAN (or of none) belongs elsewhere.
    One of the same VLAN is a pool of its own (suggest() goes through it with
    its own mask and reserved addresses), so it is left out here too.
    """
    return [(child.prefix.first, child.prefix.last) for child in prefix.get_child_prefixes().only('prefix')]


def reserved(prefix):
    """
    The addresses of a prefix never handed out, as (start, end) intervals:
    the network address and the gateway after it, and the broadcast address.
    None for /31 and /32, where every address is a host.
    """
    network = prefix.prefix
    if network.prefixlen >= 31:
        return []
    return [(network.first, network.first + 1), (network.last, network.last)]


def _used(ip_addresses, first, last):
    """Numbers of the existing addresses from first to last."""
    numbers = (int(address.ip) for address in ip_addresses.values_list('address', flat=True))
    return [n for n in numbers if first <= n <= last]


def free_number(first, last, taken, used, order, fill_gaps):
    """
    The next free number from first to last, or None.

    taken: (start, end) intervals that are not free; they may overlap and
    stick out of the bounds. used: the used addresses. Without fill_gaps,
    AFTER_LAST only looks above the highest used address and BEFORE_FIRST
    below the lowest, so gaps between used addresses stay empty. Then the
    lowest (AFTER_LAST) or highest (BEFORE_FIRST) free number wins.
    """
    downwards = order == AddressOrderChoices.BEFORE_FIRST
    if used and not fill_gaps:
        if downwards:
            last = min(last, min(used) - 1)
        else:
            first = max(first, max(used) + 1)
    if downwards:
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


def parse_address(text):
    """
    The IPv4 address typed in the popup ('10.0.0.5', a mask is ignored), as a
    netaddr.IPAddress, or None when it is empty or not an IPv4 address.
    """
    text = (text or '').strip().split('/')[0]
    try:
        address = netaddr.IPAddress(text, version=4, flags=netaddr.INET_PTON)
    except (netaddr.AddrFormatError, ValueError, TypeError):
        return None
    return address


def containing_prefixes(address):
    """The active prefixes that hold address (a netaddr.IPAddress), the smallest first."""
    prefixes = Prefix.objects.filter(
        status=PrefixStatusChoices.STATUS_ACTIVE, prefix__net_contains_or_equals=str(address),
    ).select_related('vlan', 'vrf', 'tenant')
    return sorted(prefixes, key=lambda prefix: prefix.prefix.prefixlen, reverse=True)


def check_address(vlan, text):
    """
    The address typed in the popup, as a Suggestion for the VLAN: with the
    mask of the VLAN's smallest prefix that holds it, or a problem (a key
    of TYPED_PROBLEMS). Free means the same as for suggest(): no IP address
    object in the prefix's VRF and not in a populated range.
    """
    address = parse_address(text)
    if address is None:
        return Suggestion(problem='bad-address')
    prefix = next((prefix for prefix in containing_prefixes(address) if prefix.vlan_id == vlan.pk), None)
    number = int(address)
    # Inside a smaller prefix of another VLAN (one of the same VLAN would have been found first).
    if prefix is None or any(start <= number <= end for start, end in child_prefixes(prefix)):
        return Suggestion(problem='not-in-vlan')
    if any(start <= number <= end for start, end in reserved(prefix)):
        return Suggestion(problem='reserved', prefix=prefix)
    populated = prefix.get_child_ranges(mark_populated=True)
    if IPAddress.objects.filter(vrf=prefix.vrf, address__net_host=str(address)).exists() or any(
        int(r.start_address.ip) <= number <= int(r.end_address.ip) for r in populated
    ):
        return Suggestion(problem='taken', prefix=prefix)
    iprange = next((
        r for r in prefix_ranges(prefix) if int(r.start_address.ip) <= number <= int(r.end_address.ip)
    ), None)
    return Suggestion(address=f'{address}/{prefix.prefix.prefixlen}', prefix=prefix, range=iprange)
