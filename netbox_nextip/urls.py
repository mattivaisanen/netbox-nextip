from django.urls import include, path

from utilities.urls import get_model_urls

from . import views

urlpatterns = [
    path('rules/', include(get_model_urls('netbox_nextip', 'iprule', detail=False))),
    path('rules/<int:pk>/', include(get_model_urls('netbox_nextip', 'iprule'))),
    path('add-ip/device/<int:pk>/', views.DeviceAddIPView.as_view(), name='add_ip_device'),
    path('add-ip/virtual-machine/<int:pk>/', views.VirtualMachineAddIPView.as_view(), name='add_ip_virtualmachine'),
    path('add-ip/device/<int:pk>/popup/', views.DeviceAddIPPopupView.as_view(), name='add_ip_popup_device'),
    path(
        'add-ip/virtual-machine/<int:pk>/popup/', views.VirtualMachineAddIPPopupView.as_view(),
        name='add_ip_popup_virtualmachine',
    ),
]
