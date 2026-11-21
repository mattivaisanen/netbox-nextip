from django.utils.translation import gettext_lazy as _

from netbox.plugins import PluginMenuButton, PluginMenuItem

# One entry under NetBox's Plugins menu (named in NextIPConfig.menu_items).
menu_items = (
    PluginMenuItem(
        link='plugins:netbox_nextip:iprule_list',
        link_text=_('IP Rules'),
        permissions=['netbox_nextip.view_iprule'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_nextip:iprule_add',
                title=_('Add'),
                icon_class='mdi mdi-plus-thick',
                permissions=['netbox_nextip.add_iprule'],
            ),
        ),
    ),
)
