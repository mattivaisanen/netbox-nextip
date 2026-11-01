from netbox.plugins import PluginMenuButton, PluginMenuItem

menu_items = (
    PluginMenuItem(
        link='plugins:netbox_nextip:iprule_list',
        link_text='IP Rules',
        permissions=['netbox_nextip.view_iprule'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_nextip:iprule_add',
                title='Add',
                icon_class='mdi mdi-plus-thick',
                permissions=['netbox_nextip.add_iprule'],
            ),
        ),
    ),
)
