"""
The names a rule's templates make: the new interface's name and the new
address's DNS name. Both are Python format strings with fixed fields.
"""
import re
import string

from django.utils.text import slugify
from django.utils.translation import gettext as _

# Highest {n} tried before giving up (a device with this many interfaces of one pattern is a mistake).
MAX_N = 4096

# Widest padding a template field may ask for, such as {n:03} or {vid:>4}. Interface names have 64
# characters at most; a huge width would build a huge string.
MAX_WIDTH = 64


def interface_name(rule, existing_names):
    """
    The name of the interface the address goes on. With {n} in the
    template, the lowest n from 0 that is not in existing_names; None when
    all are taken.
    """
    fields = {'vid': rule.vlan.vid, 'vlan': rule.vlan.name}
    if 'n' not in field_names(rule.interface_name):
        return rule.interface_name.format(n=0, **fields)
    for n in range(MAX_N):
        name = rule.interface_name.format(n=n, **fields)
        if name not in existing_names:
            return name
    return None


def dns_name(rule, obj, interface_name):
    """
    The rule's DNS name template filled in, or '' when there is none.
    Each part becomes a DNS label, so 'Gi1/0/1' becomes 'gi1-0-1'; empty
    labels are dropped.
    """
    device = '.'.join(_label(part) for part in (obj.name or '').split('.'))
    if not rule.dns_name or not device.strip('.'):
        # No name, or one with nothing left as a DNS label ('...'): no DNS name, rather than the bare domain.
        return ''
    site = getattr(obj, 'site', None)
    name = rule.dns_name.format(
        # A device named as an FQDN keeps its dots: 'sw1.lab' stays 'sw1.lab'.
        device=device,
        interface=_label(interface_name),
        vid=rule.vlan.vid,
        vlan=_label(rule.vlan.name),
        site=site.slug if site else '',
    ).lower()
    # An empty field (a VM without a site) or a stray dot in a device name leaves empty labels:
    # 'sw1..example.com' becomes 'sw1.example.com'. A trailing dot (a rooted name) stays.
    rooted = name.endswith('.')
    name = '.'.join(label for label in name.split('.') if label)
    return name + '.' if rooted and name else name


def check_interface_name(template):
    """An error message when the interface name template has an unknown field, else None."""
    return _check(template, n=0, vid=0, vlan='')


def check_dns_name(template):
    """An error message when the DNS name template has an unknown field or text a DNS name can't have."""
    try:
        text = ''.join(literal for literal, _name, _spec, _conv in string.Formatter().parse(template))
    except ValueError:
        text = ''  # _check() reports the bad template
    if not re.fullmatch(r'[A-Za-z0-9._-]*', text):
        return _('Only letters, digits, dots, hyphens and underscores may stand between the fields.')
    return _check(template, device='', interface='', vid=0, vlan='', site='')


def field_names(template):
    """The field names a template uses: 'oob{n:02}' gives {'n'}. Empty for a bad template."""
    try:
        return {name for _text, name, _spec, _conv in string.Formatter().parse(template) if name is not None}
    except ValueError:
        return set()


def _check(template, **fields):
    try:
        for _text, name, spec, conversion in string.Formatter().parse(template):
            if name is not None and not name.isidentifier():
                # No positional fields, attributes or indexes: {0}, {vlan.upper}, {vlan[0]}.
                return _('Use only the named fields, such as {{vid}}: {name!r} is not one.').format(name=name)
            if conversion:
                return _('Field {name}: conversions such as !r are not allowed.').format(name=name)
            if spec and '{' in spec:
                return _('Field {name}: fields inside a format spec are not allowed.').format(name=name)
            if spec and any(int(width) > MAX_WIDTH for width in re.findall(r'\d+', spec)):
                return _('Field {name} is padded wider than {max} characters.').format(name=name, max=MAX_WIDTH)
        template.format(**fields)
    except (KeyError, IndexError, ValueError, TypeError) as error:
        return _('Unknown field or bad template: {error}').format(error=error)
    return None


def _label(text):
    """text as a DNS label: 'Gi1/0/1.100' becomes 'gi1-0-1-100'."""
    for char in '/._':
        text = text.replace(char, '-')
    return slugify(text)
