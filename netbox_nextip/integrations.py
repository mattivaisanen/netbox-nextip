"""
Optional plugins this one works with. Each is detected with
apps.is_installed(), so a package that is installed but not in PLUGINS is
left alone, and imported only when used.
"""
import logging

from django.apps import apps

logger = logging.getLogger(__name__)


def has_change_approval():
    """True when netbox-change-approval is enabled in PLUGINS."""
    return apps.is_installed('netbox_change_approval')


def change_approval_context():
    """
    netbox-change-approval's (batch_scope, current_batch), or None when the
    plugin is not enabled or its API has moved (logged, so it is noticed).
    """
    if not has_change_approval():
        return None
    try:
        from netbox_change_approval.context import batch_scope, current_batch
    except ImportError:
        logger.warning('netbox-change-approval is enabled but has no batch_scope; Add IP is not batched')
        return None
    return batch_scope, current_batch
