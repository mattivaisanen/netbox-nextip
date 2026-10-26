from django.urls import include, path

from utilities.urls import get_model_urls

from . import views

urlpatterns = [
    path('rules/', include(get_model_urls('netbox_nextip', 'suggestionrule', detail=False))),
    path('rules/<int:pk>/', include(get_model_urls('netbox_nextip', 'suggestionrule'))),
    path('assign/device/<int:pk>/', views.DeviceAssignView.as_view(), name='assign_device'),
    path('assign/virtual-machine/<int:pk>/', views.VirtualMachineAssignView.as_view(), name='assign_virtualmachine'),
]
