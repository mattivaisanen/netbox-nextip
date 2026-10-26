from django.urls import path

from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.register('rules', views.SuggestionRuleViewSet)

urlpatterns = [
    path('next-ip/', views.NextIPView.as_view(), name='next-ip'),
    *router.urls,
]
