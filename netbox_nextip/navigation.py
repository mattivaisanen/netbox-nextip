from netbox.plugins import PluginMenuButton, PluginMenuItem

menu_items = (
    PluginMenuItem(
        link='plugins:netbox_nextip:suggestionrule_list',
        link_text='IP Suggestion Rules',
        permissions=['netbox_nextip.view_suggestionrule'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_nextip:suggestionrule_add',
                title='Add',
                icon_class='mdi mdi-plus-thick',
                permissions=['netbox_nextip.add_suggestionrule'],
            ),
        ),
    ),
)
