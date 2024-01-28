from django.contrib import admin
from django.urls import include, path
from rest_framework import routers

from circle.api.direct_message.viewsets import (
    MessageAbuseView,
    NotifyRedirectViewSet,
    XMPPChatViewSet,
    XMPPMessageFilterViewSet,
    XMPPMessageViewSet,
)
from circle.api.media_views.viewsets import (
    ChatAudioUploadViewSet,
    ChatDocumentsUploadViewSet,
    ChatImageUploadViewSet,
    ChatVideoUploadViewSet,
    GroupImageUploadViewSet,
)
from circle.api.viewsets import (
    AppBrandingViewSet,
    CircleInviteViewSet,
    CirclePermissionViewSet,
    CircleSubscriberRoleViewSet,
    CircleViewSet,
    CustomerViewSet,
    CustomFieldViewSet,
    GetCircleUniqueNameView,
    HierarchyDeleteAPIView,
    HierarchyTransferAPIView,
    CircleInviteViewSet,
    CircleInviteAcceptViewSet,
    SubscriptionPlanViewSet,
    TopicViewSet,
    CircleLevelNameConfViewSet,
    GetAssociatedCircles,
)

router = routers.SimpleRouter()
router.register(r"circle", CircleViewSet, basename="circle"),
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
router.register(r"subscription-plan", SubscriptionPlanViewSet, basename="subscription-plan"),
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

router.register(r"s3groupimageparams", GroupImageUploadViewSet, basename="s3groupimageparams")
router.register(r"s3chatimageparams", ChatImageUploadViewSet, basename="s3chatimageparams")
router.register(r"s3chatvideoparams", ChatVideoUploadViewSet, basename="s3chatvideoparams")
router.register(r"s3chatdocsparams", ChatDocumentsUploadViewSet, basename="s3chatdocsparams")
router.register(r"s3chataudioparams", ChatAudioUploadViewSet, basename="s3chataudioparams")
router.register(r"circle_invite", CircleInviteViewSet, basename="circle-invite")
router.register(r"hierarchy/level_name", CircleLevelNameConfViewSet, basename="circle-level-name")

urlpatterns = [
    path("admin/", admin.site.urls),
    path(r"", include(router.urls)),
    path(
        r"xmpp_chat/",
        XMPPChatViewSet.as_view({"get": "list"}),
        name="xmpp_chat",
    ),
    path(
        r"notify_redirect/",
        NotifyRedirectViewSet.as_view(),
        name="push_notify_redirect",
    ),
    # hierarchy
    path(r"hierarchy_delete/", HierarchyDeleteAPIView.as_view(), name="hierarchy_delete"),
    path(
        r"hierarchy_transfer/",
        HierarchyTransferAPIView.as_view(),
        name="hierarchy_transfer",
    ),
    path(r"msg/abuse/", MessageAbuseView.as_view(), name="message-abuse"),
    path(
        r"circle_invite_accept/",
        CircleInviteAcceptViewSet.as_view(),
        name="circle-invite-accept",
    ),
    path(r"get_circle_name/", GetCircleUniqueNameView.as_view(), name="group-unique-name"),
    path(r"associated/", GetAssociatedCircles.as_view(), name="user-associated-circles"),
]
