from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.register('rules', views.IPRuleViewSet)

urlpatterns = router.urls
