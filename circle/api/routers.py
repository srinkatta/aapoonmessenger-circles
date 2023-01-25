from django.urls import include, path
from rest_framework import routers

from circle.api.direct_message.viewsets import (
    MuteMessageView,
    XMPPChatViewSet,
    XMPPDeleteDMViewSet,
    XMPPMessageFilterViewSet,
    XMPPMessageViewSet,
    XMPPMonthlyChatViewSet,
)

from circle.api.media.viewsets import (
    GroupImageUploadViewSet,
    ChatImageUploadViewSet,
    ChatVideoUploadViewSet,
    ChatDocumentsUploadViewSet,
    ChatAudioUploadViewSet,
)
from circle.api.viewsets import (
    AppBrandingViewSet,
    CircleRoleViewSet,
    CircleSubscriberRoleViewSet,
    CircleViewSet,
    CustomerViewSet,
    CustomFieldViewSet,
    SubscriptionPlanViewSet,
    TopicViewSet,
    CirclePermissionViewSet,
    HierarchyDeleteAPIView,
    HierarchyTransferAPIView,
)

router = routers.SimpleRouter()
router.register(r"circle", CircleViewSet, basename="circle"),
router.register(r"circle/role", CircleRoleViewSet, basename="circle-role")
router.register(
    r"circle/(?P<circle_id>\d+)/assign-role",
    CircleSubscriberRoleViewSet,
    basename="circles-subscriber-role",
),

router.register(
    r"circle/(?P<circle_id>\d+)/permissions",
    CirclePermissionViewSet,
    basename="circle-permissions",
),
router.register(
    r"subscription-plan", SubscriptionPlanViewSet, basename="subscription-plan"
),
router.register(r"customer", CustomerViewSet, basename="customer"),
router.register(r"app-branding", AppBrandingViewSet, basename="app-branding"),
router.register(
    r"circle/(?P<circle_id>\d+)/custom-field",
    CustomFieldViewSet,
    basename="custom-field",
),
router.register(r"topic", TopicViewSet, basename="topic"),
router.register(r"messages", XMPPMessageViewSet, basename="xmpp_messages")
router.register(r"get_messages", XMPPMessageFilterViewSet, basename="get_messages")

router.register(
    r"s3groupimageparams", GroupImageUploadViewSet, basename="s3groupimageparams"
)
router.register(
    r"s3chatimageparams", ChatImageUploadViewSet, basename="s3chatimageparams"
)
router.register(
    r"s3chatvideoparams", ChatVideoUploadViewSet, basename="s3chatvideoparams"
)
router.register(
    r"s3chatdocsparams", ChatDocumentsUploadViewSet, basename="s3chatdocsparams"
)
router.register(
    r"s3chataudioparams", ChatAudioUploadViewSet, basename="s3chataudioparams"
)

urlpatterns = [
    path(r"", include(router.urls)),
    path(r"mute_messages/", MuteMessageView.as_view()),
    path(
        r"xmpp_chat/",
        XMPPChatViewSet.as_view({"get": "list"}),
        name="xmpp_chat",
    ),
    path(
        r"xmpp_monthly_chat/",
        XMPPMonthlyChatViewSet.as_view({"get": "list"}),
        name="xmpp_chat",
    ),
    path(r"delete_chat/", XMPPDeleteDMViewSet.as_view(), name="delete_chat"),
    # hierarchy
    path(
        r"hierarchy_delete/", HierarchyDeleteAPIView.as_view(), name="hierarchy_delete"
    ),
    path(
        r"hierarchy_transfer/",
        HierarchyTransferAPIView.as_view(),
        name="hierarchy_transfer",
    ),
]
