from circle.api.routers import urlpatterns as circle_urlpatterns
from circle.api.admin.routers import urlpatterns as admin_urlpatterns

router_urlpatterns = []
router_admin_urlpatterns = []

router_urlpatterns += circle_urlpatterns
router_admin_urlpatterns += admin_urlpatterns
