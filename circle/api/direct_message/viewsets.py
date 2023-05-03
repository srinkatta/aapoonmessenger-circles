import ast
import logging
import threading
import time

from django.core.exceptions import ObjectDoesNotExist
from django.db import connections
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_api_key.permissions import HasAPIKey

from circle.api.direct_message.serializers import (
    ArchiveChatSerializer,
    ChatMessageFilterInputSerializer,
    ChatMessageFilterSerializer,
    ChatMessageSerializer,
    MessageAbuseSerializer,
    NotifyRedirectSerializer,
)
from circle.api.utils import abuse_mail_msg
from circle.helpers.notifications import app_notification
from circle.middleware.permissions import Authenticate
from circle.models import ChatMessage
from circle.services.user import user_notify_chat
from circle_service import settings

logger = logging.getLogger(__name__)


class XMPPMessageViewSet(viewsets.ModelViewSet):
    """
    API View to list and create messages from and in XMPP.
    """

    model = ChatMessage
    serializer_class = ChatMessageSerializer
    http_method_names = ["get", "post"]

    def list(self, request, *args, **kwargs):
        if "message_id" in request.GET:
            message_ids = request.GET["message_id"]
            message_ids = ast.literal_eval(message_ids)
            queryset = (
                ChatMessage.objects.filter(message_id__in=message_ids)
                .values("message_id")
                .distinct()
            )
        else:
            queryset = ChatMessage.objects.values("message_id").distinct()
        paginated_qs = self.paginate_queryset(queryset)
        serializer = ChatMessageSerializer(paginated_qs, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        message_id = request.data["message_id"]
        action = request.data["action"]
        actions = ["like", "dislike"]
        is_exists = True
        if action in actions:
            chat_messages = ChatMessage.objects.filter(
                message_id=message_id, action_by=request.user_id, action=action
            )
            if chat_messages:
                chat_messages.delete()
                is_exists = False
            self.update_like_dislike(
                message_id=message_id, user_id=request.user_id, action=action
            )
        if is_exists:
            request.data["action_by"] = request.user_id

            serializer = ChatMessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            print(serializer.initial_data)
            try:
                serializer.save()
                return Response(
                    {"success": True, "message": "Message stored successfully"}
                )
            except Exception as e:
                return Response(
                    {
                        "success": False,
                        "message": "Error occurred while saving the message {}".format(
                            e
                        ),
                    }
                )
        else:
            return Response(
                {
                    "success": False,
                    "message": "The fields message_id, action, action must make a unique set for like, dislike and "
                    "forward.",
                }
            )

    def update_like_dislike(self, message_id, user_id, action):
        try:
            chat_msg = ChatMessage.objects.filter(
                message_id=message_id, action_by=user_id
            )
            if chat_msg:
                if chat_msg[0].action == "like" and action == "dislike":
                    chat_msg.delete()
                    ChatMessage.objects.filter(
                        message_id=message_id, action_by=user_id
                    ).update(action=action)
                elif chat_msg[0].action == "dislike" and action == "like":
                    chat_msg.delete()
                    ChatMessage.objects.filter(
                        message_id=message_id, action_by=user_id
                    ).update(action=action)
        except ObjectDoesNotExist as e:
            logging.exception("ObjectDoesNotExist: %s", e)

    def retrieve(self, request, *args, **kwargs):
        queryset = ChatMessage.objects.filter(message_id=kwargs.get("pk"))
        if queryset.exists():
            serializer = ChatMessageSerializer(
                {"message_id": queryset.first().message_id}
            )
            return Response(serializer.data)
        else:
            return Response(
                {
                    "success": False,
                    "message": "No message found for provided message_id",
                }
            )


class XMPPMessageFilterViewSet(viewsets.ModelViewSet):
    model = ChatMessage
    serializer_class = ChatMessageFilterInputSerializer
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        message_ids = request.data.get("message_id", [])
        queryset = (
            ChatMessage.objects.filter(message_id__in=message_ids)
            .values("message_id")
            .distinct()
        )

        serializer = ChatMessageFilterSerializer(queryset, many=True)
        return Response(serializer.data)


class ArchiveChat(object):
    def __init__(self, **kwargs):
        for field in ("id", "bare_peer", "timestamp", "xml", "username", "user_pic"):
            setattr(self, field, kwargs.get(field))


class CustomPagination(PageNumberPagination):
    def get_paginated_response(self, data):
        return Response({"results": data})


class XMPPChatViewSet(viewsets.ViewSet, CustomPagination):
    serializer_class = ArchiveChatSerializer
    http_method_names = ["get"]

    def direct_query(self, request, timestamp, length):
        peer = request.query_params.get("peer")
        username = request.query_params.get("username")
        peer_split = peer.split("@")
        friend_peer = username + "@" + peer_split[1]
        friend_username = peer_split[0]
        query = (
            "SELECT id, timestamp,xml FROM archive WHERE (peer='"
            + peer
            + "' AND username='"
            + username
            + "') OR "
            "(peer='"
            + friend_peer
            + "' AND username='"
            + friend_username
            + "') AND timestamp<"
            + timestamp
            + " ORDER BY timestamp desc LIMIT "
            + str(length)
            + ";"
        )

        return query

    def conference_query(self, request, timestamp, length):
        conference_id = request.query_params.get("conference_id")
        query = (
            "SELECT id, timestamp,xml FROM archive WHERE username='"
            + conference_id
            + "' AND timestamp<"
            + timestamp
            + " ORDER BY timestamp desc LIMIT "
            + str(length)
            + ";"
        )
        return query

    def fetch_archive_chat(self, query):
        with connections["xmpp_database"].cursor() as cursor:
            cursor.execute(query)
            archive_data = cursor.fetchall()
            archive_data = sorted(archive_data, key=lambda x: x[0])
            archive_chat = [
                ArchiveChat(id=archive[0], timestamp=archive[1], xml=archive[2])
                for archive in archive_data
            ]
            return archive_chat

        return []

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="type",
                description="type",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="conference_id",
                description="conference_id",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="peer",
                description="Peer",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="username",
                description="username",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="length",
                description="length",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="timestamp",
                description="timestamp",
                required=False,
                type=str,
            ),
        ],
    )
    def list(self, request):
        # Timestamp and Length
        timestamp = request.query_params.get("timestamp")
        length = request.query_params.get("length")
        length = 50 if not length else length

        timestamp = timestamp if timestamp else str(time.time() * 1000 * 1000)

        type = request.query_params.get("type", "")
        if type == "DIRECT":
            q = self.direct_query(request, timestamp, length)
        else:
            q = self.conference_query(request, timestamp, length)
        try:
            archive_chat = self.fetch_archive_chat(q)
            page = self.paginate_queryset(archive_chat, request)
            serializer = self.serializer_class(instance=page, many=True)
            return self.get_paginated_response(serializer.data)
        except Exception:
            return Response(
                {"data": "Invalid Conference Id"}, status=status.HTTP_200_OK
            )


class NotifyRedirectViewSet(APIView):
    http_method_names = ["post"]
    serializer_class = NotifyRedirectSerializer
    permission_classes = [HasAPIKey]

    def post(self, request):
     
        message = request.data["body"]
        message_from = request.data["from"]
        to = request.data["to"]
        xml = request.data.get("xml")

        if "vhost" in request.data:
            if request.data["vhost"] == settings.XMPP_HOST:
                user_notify_chat(message, message_from, to, xml)

            if request.data["vhost"] == "conference" + "." + settings.XMPP_HOST:
                topic_name = request.data.get("to")
                t = threading.Thread(
                    target=app_notification,
                    args=(topic_name, message_from, message, xml),
                )
                t.start()
        return Response({"data": "Notification sent."}, status=200)


class MessageAbuseView(APIView):
    """
    API View to mute receiving messages from some other user.
    """

    permission_classes = (Authenticate,)
    allowed_methods = ("POST",)
    serializer_class = MessageAbuseSerializer

    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            abuse_mail_msg(serializer.data)
            return Response({"data": "Mail sent Successfully"}, status=200)
        except Exception as exc:
            logger.error(exc)
            logger.exception(exc)

