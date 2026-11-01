from django.utils.translation import gettext_lazy as _

from utilities.choices import ChoiceSet


class RuleObjectChoices(ChoiceSet):
    """What a rule is for."""
    DEVICE = 'device'
    VIRTUAL_MACHINE = 'virtualmachine'

    CHOICES = (
        (DEVICE, _('Devices')),
        (VIRTUAL_MACHINE, _('Virtual machines')),
    )


class AddressOrderChoices(ChoiceSet):
    """
    Where the next address is taken from. Without fill_gaps, free addresses
    between used ones are skipped: AFTER_LAST continues after the highest
    used address, BEFORE_FIRST below the lowest one. With fill_gaps, the
    lowest (or highest) free address is used.
    """
    AFTER_LAST = 'after-last'
    BEFORE_FIRST = 'before-first'

    CHOICES = (
        (AFTER_LAST, _('Upwards, after the last used address')),
        (BEFORE_FIRST, _('Downwards, before the first used address')),
    )
