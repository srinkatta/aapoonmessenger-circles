import ast
import logging
import threading
import time

from django.db import connections
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from circle.api.direct_message.serializers import (
    ArchiveChatSerializer,
    ChatMessageFilterInputSerializer,
    ChatMessageFilterSerializer,
    ChatMessageSerializer,
    MessageAbuseSerializer,
    MuteMessageSerializer,
    NotifyRedirectSerializer,
)
from circle.api.utils import abuse_mail_msg
from circle.helpers.notifications import app_notification, notify_dm
from circle.middleware.permissions import Authenticate
from circle.models import ChatMessage, MuteCoversation
from circle.services.user import User
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
        chat_msg = ChatMessage.objects.filter(message_id=message_id, action_by=user_id)
        if chat_msg:
            try:
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
            except:
                pass

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


class MuteMessageView(APIView):
    """
    API View to mute receiving messages from some other user.
    """

    permission_classes = (AllowAny,)
    allowed_methods = ("POST", "GET")
    serializer_class = MuteMessageSerializer

    def get(self, request, *args, **kwargs):
        params = request.GET
        if "mute" in params and "recipient" in params and "sender" in params:
            sender = params.get("sender") + "@" + settings.XMPP_HOST
            recipient = params.get("recipient") + "@" + settings.XMPP_HOST
            message = MuteCoversation.objects.filter(
                sender_id=sender, recipient_id=recipient, mute=True
            )
            serializer = MuteMessageSerializer(message, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"data": "Field missing in Query params."}, status=status.HTTP_200_OK
        )

    def post(self, request):
        data = request.data
        sender = data.get("sender_id")
        sender = str(sender) + "@" + settings.XMPP_HOST
        recipient = data.get("recipient_id")
        recipient = str(recipient) + "@" + settings.XMPP_HOST
        mute_time = data.get("mute_time")
        mute = data.get("mute")
        if MuteCoversation.objects.filter(
            sender_id=sender, recipient_id=recipient
        ).exists():
            message = MuteCoversation._default_manager.get(
                sender_id=sender, recipient_id=recipient
            )
            message.mute_time = mute_time
            message.mute = mute
            message.save()
            serializer = MuteMessageSerializer(message)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            serializer = MuteMessageSerializer(data=request.data)
            if serializer.is_valid():
                serializer.validated_data["sender_id"] = sender
                serializer.validated_data["recipient_id"] = recipient
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_403_FORBIDDEN)


class ArchiveChat(object):
    def __init__(self, **kwargs):
        for field in ("id", "bare_peer", "timestamp", "xml", "username", "user_pic"):
            setattr(self, field, kwargs.get(field, None))


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
            archive_res = cursor.execute(query)
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


class XMPPMonthlyChatViewSet(viewsets.ViewSet, CustomPagination):
    serializer_class = ArchiveChatSerializer
    http_method_names = ["get"]

    def fetch_archive_data(self, query, username):
        archive_data = []
        with connections["xmpp_database"].cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                bare_peer = row[0]

                peer_split = bare_peer.split("@")
                f_bare_peer = username + "@" + peer_split[1]
                f_username = peer_split[0]

                q = (
                    "SELECT DISTINCT bare_peer, LAST_VALUE(xml) OVER (PARTITION BY bare_peer) FROM archive WHERE kind='chat' AND "
                    "(username='"
                    + username
                    + "' AND bare_peer='"
                    + bare_peer
                    + "') OR (username='"
                    + f_username
                    + "' AND  bare_peer='"
                    + f_bare_peer
                    + "'); "
                )
                cursor.execute(q)
                last_value = cursor.fetchall()
                last_list = list(last_value[0])
                last_list.append(bare_peer)
                archive_data.append(last_list)
        return archive_data

    def fetch_archive_chat(self, archive_data):
        archive_chat = []
        for archive in archive_data:
            # TODO: get user details from user microservice
            user = archive[-1]  # todo
            username = None
            user_pic = None
            timestamp = self.xml_timestamp_value(archive[1])
            if user:
                username = user[0].name
                user_pic = user[0].logo
            archive_chat.append(
                ArchiveChat(
                    id=0,
                    timestamp=timestamp,
                    bare_peer=archive[-1],
                    xml=archive[1],
                    username=username,
                    user_pic=user_pic,
                )
            )
        archive_sort = sorted(archive_chat, key=lambda x: x.timestamp, reverse=True)

        return archive_sort

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="username",
                description="username",
                required=True,
                type=str,
            ),
            OpenApiParameter(
                name="length",
                description="length",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="offset",
                description="offset",
                required=False,
                type=int,
            ),
        ],
    )
    def list(self, request):
        username = request.query_params.get("username")
        length = request.query_params.get("length")
        offset = request.query_params.get("offset")
        offset = offset if offset else 0
        length = length if length else 10

        exclude_bare_peer = "%conference." + settings.XMPP_HOST
        q = (
            "SELECT DISTINCT bare_peer FROM archive WHERE bare_peer NOT LIKE '"
            + exclude_bare_peer
            + "' AND username='"
            + username
            + "'LIMIT "
            + str(length)
            + " OFFSET "
            + str(offset)
            + ";"
        )
        try:
            archive_data = self.fetch_archive_data(query=q, username=username)
            archive_chat = self.fetch_archive_chat(archive_data)

            page = self.paginate_queryset(archive_chat, request)
            serializer = self.serializer_class(instance=page, many=True)
            return self.get_paginated_response(serializer.data)
        except Exception as e:
            print(e)
            return Response({"data": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def xml_timestamp_value(self, xml):
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml)
        for page in root:
            for time in page:
                if time.tag == "{urn:xmpp:time}Time":
                    epoch_time = time.text
                    return epoch_time


class XMPPDeleteDMViewSet(generics.GenericAPIView):
    serializer_class = ArchiveChatSerializer
    http_method_names = ["post"]

    def post(self, request):
        ids = request.data["ids"]
        q = "DELETE FROM archive WHERE id IN " + str(tuple(ids)) + ";"
        try:
            with connections["xmpp_database"].cursor() as cursor:
                cursor.execute(q)
            return Response(
                {"data": "Message deleted Successfully"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            print(e)
            return Response({"data": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class NotifyRedirectViewSet(generics.GenericAPIView):
    http_method_names = ["post"]
    serializer_class = NotifyRedirectSerializer

    def post(self, request):
        """
        Renamed the field `from` to `from_user` because `from` is a reserved keyword and can't be used a variable
        """
        message = request.data["body"]
        message_from = request.data["from"]
        to = request.data["to"]
        xml = request.data.get("xml")
        message_id = request.data.get("message_id")

        if "vhost" in request.data:
            if request.data["vhost"] == settings.XMPP_HOST:
                to_jid = to + "@" + settings.XMPP_HOST
                message_from = message_from + "@" + settings.XMPP_HOST
                user_service = User()
                to_user = user_service.details(user_jid=to_jid)

                if not to_user:
                    logger.error(f"No User exists with the given user_jid: {to_user}")
                    return Response(
                        {"data": "No user found"}, status=status.HTTP_404_NOT_FOUND
                    )

                from_user = user_service.details(user_jid=message_from)
                if not from_user:
                    logger.error(f"No User exists with the given user_jid: {from_user}")
                    return Response(
                        {"data": "No user found"}, status=status.HTTP_404_NOT_FOUND
                    )

                # Check for muted conversation
                if MuteCoversation.objects.filter(
                    sender_id=message_from, recipient_id=to_jid, mute=True
                ).exists():
                    print(time.time())
                    mutify = MuteCoversation.objects.filter(
                        sender_id=message_from, recipient_id=to_jid, mute=True
                    ).first()
                    if time.time() > mutify.mute_time:
                        print("Mute expired")
                        notify_dm(to_user, from_user, message_from, message, xml)
                    else:
                        print("Mute notification")
                        pass
                else:
                    print("No Mute")
                    notify_dm(to_user, from_user, message_from, message, xml)
            elif request.data["vhost"] == "conference" + "." + settings.XMPP_HOST:
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
