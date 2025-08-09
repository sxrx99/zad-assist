
from rest_framework_nested import routers
from . import views
# from .routing import websocket_urlpatterns

router = routers.SimpleRouter()
router.register("companies", views.CompanyViewSet)
router.register("customers", views.CustomerViewSet, basename="customers")
router.register("operators", views.OperatorViewSet, basename="operators")
router.register('documents', views.DocumentViewSet, basename='document')

# URLConf
urlpatterns = router.urls
# urlpatterns += websocket_urlpatterns
