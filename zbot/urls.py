
from rest_framework_nested import routers
from . import views

router = routers.SimpleRouter()
router.register("conversations", views.ConversationViewSet, basename="conversations")
router.register("machines", views.MachineViewSet, basename="machines")
router.register("bugreports", views.BugReportViewSet, basename="bugreports")
router.register("materials", views.MaterialViewSet, basename="materials")


conversation_router = routers.NestedSimpleRouter(router, "conversations", lookup="conversation")

conversation_router.register("imageMessages", views.ImageMessageViewSet, basename="conversation-imageMessages")
conversation_router.register("textMessages", views.TextMessageViewSet, basename="conversation-textMessages")
conversation_router.register("parameters", views.MachineParameterViewSet, basename="converation-parameters")
#conversation_router.register('stream', views.ConversationViewSet, basename='conversation-stream')


urlpatterns = router.urls + conversation_router.urls 
