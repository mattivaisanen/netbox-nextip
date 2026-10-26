"""Plugin settings: PLUGINS_CONFIG['netbox_nextip'], with defaults from
NextIPConfig.default_settings."""
from netbox.plugins.utils import get_plugin_config

PLUGIN = 'netbox_nextip'


def get_setting(key):
    return get_plugin_config(PLUGIN, key)
