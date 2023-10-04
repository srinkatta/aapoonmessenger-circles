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

    permission_classes = (Authenticate,)
    model = ChatMessage
    serializer_class = ChatMessageSerializer
    http_method_names = ["get", "post"]

    def list(self, request, *args, **kwargs):
        """
        List XMPP messages.

        Args:
            request: The request object.
            *args: Variable length argument list.
            **kwargs: Keyword arguments.

        Returns:
            Response: A paginated response containing the list of XMPP messages.
        """
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
        """
        Create a new XMPP message.

        Args:
            request: The request object.
            *args: Variable length argument list.
            **kwargs: Keyword arguments.

        Returns:
            Response: A response indicating successful message creation.
        """
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
            self.update_like_dislike(message_id=message_id, user_id=request.user_id, action=action)
        if is_exists:
            request.data["action_by"] = request.user_id

            serializer = ChatMessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            print(serializer.initial_data)
            try:
                serializer.save()
                return Response({"success": True, "message": "Message stored successfully"})
            except Exception as e:
                return Response(
                    {
                        "success": False,
                        "message": "Error occurred while saving the message {}".format(e),
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
        """
        Update the like/dislike action of a specific XMPP message for a given user.

        Args:
            message_id (str): The ID of the XMPP message.
            user_id (int): The ID of the user performing the action.
            action (str): The new action (like or dislike) to be updated.

        Returns:
            None
        """
        try:
            chat_msg = ChatMessage.objects.filter(message_id=message_id, action_by=user_id)
            if chat_msg:
                if chat_msg[0].action == "like" and action == "dislike":
                    chat_msg.delete()
                    ChatMessage.objects.filter(message_id=message_id, action_by=user_id).update(
                        action=action
                    )
                elif chat_msg[0].action == "dislike" and action == "like":
                    chat_msg.delete()
                    ChatMessage.objects.filter(message_id=message_id, action_by=user_id).update(
                        action=action
                    )
        except ObjectDoesNotExist as e:
            logging.exception("ObjectDoesNotExist: %s", e)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific XMPP message.

        Args:
            request: The request object.
            *args: Variable length argument list.
            **kwargs: Keyword arguments.

        Returns:
            Response: A response containing the details of the retrieved XMPP message.
        """
        queryset = ChatMessage.objects.filter(message_id=kwargs.get("pk"))
        if queryset.exists():
            serializer = ChatMessageSerializer({"message_id": queryset.first().message_id})
            return Response(serializer.data)
        else:
            return Response(
                {
                    "success": False,
                    "message": "No message found for provided message_id",
                }
            )


class XMPPMessageFilterViewSet(viewsets.ModelViewSet):
    """
    Viewset to filter XMPP messages based on message IDs.
    """

    model = ChatMessage
    serializer_class = ChatMessageFilterInputSerializer
    http_method_names = ["post"]
    permission_classes = (Authenticate,)

    def create(self, request, *args, **kwargs):
        """
        Filter XMPP messages based on message IDs.

        Args:
            request: The request object.
            *args: Variable length argument list.
            **kwargs: Keyword arguments.

        Returns:
            Response: A response containing filtered XMPP messages based on message IDs.
        """
        message_ids = request.data.get("message_id", [])
        queryset = (
            ChatMessage.objects.filter(message_id__in=message_ids).values("message_id").distinct()
        )

        serializer = ChatMessageFilterSerializer(queryset, many=True)
        return Response(serializer.data)


class ArchiveChat(object):
    """
    Represents an archived chat.

    This class provides a convenient way to store and access the attributes of an archived chat.

    Args:
        **kwargs: Keyword arguments containing the attributes of the archived chat.

    Attributes:
        id (int): The ID of the archived chat.
        bare_peer (str): The bare peer of the archived chat.
        timestamp (datetime.datetime): The timestamp of the archived chat.
        xml (str): The XML content of the archived chat.
        username (str): The username associated with the archived chat.
        user_pic (str): The user profile picture associated with the archived chat.
    """

    def __init__(self, **kwargs):
        data = {
            "id": None,
            "bare_peer": None,
            "timestamp": None,
            "xml": None,
            "username": None,
            "user_pic": None,
        }
        for field in data:
            setattr(self, field, kwargs.get(field, data[field]))


class CustomPagination(PageNumberPagination):
    """
    Custom pagination class for API responses.

    This class extends the Django Rest Framework's PageNumberPagination to provide custom pagination for API responses.

    Methods:
        get_paginated_response(data): Returns a custom paginated response with the specified data.

    Attributes:
        page_size (int): The number of items to include in a page of results.
        page_size_query_param (str): The query parameter used to specify the page size in the request.
    """

    def get_paginated_response(self, data):
        """
        Returns a custom paginated response with the specified data.

        Args:
            data (list): The data to be included in the paginated response.

        Returns:
            Response: A response containing the paginated data.
        """
        return Response({"results": data})


class XMPPChatViewSet(viewsets.ViewSet, CustomPagination):
    """
    API ViewSet for XMPP chat messages.

    This class provides API endpoints to query and fetch XMPP chat messages.

    Attributes:
        serializer_class: The serializer class used for serializing chat message data.
        http_method_names (list): The allowed HTTP methods for this ViewSet.
    """

    serializer_class = ArchiveChatSerializer
    http_method_names = ["get"]

    def direct_query(self, request, timestamp, length):
        """
        Generate a direct query to retrieve XMPP chat messages between two peers.

        Args:
            request: The request object containing query parameters.
            timestamp (int): The timestamp representing the latest message to retrieve.
            length (int | str): The maximum number of messages to fetch.

        Returns:
            str: A SQL query to retrieve direct XMPP chat messages.
        """
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
        """
        Generate a query to retrieve XMPP chat messages in a conference.

        Args:
            request: The request object containing query parameters.
            timestamp (int): The timestamp representing the latest message to retrieve.
            length (int | str): The maximum number of messages to fetch.

        Returns:
            str: A SQL query to retrieve conference XMPP chat messages.
        """
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
        """
        Fetch XMPP chat messages from the database using the provided query.

        Args:
            query (str): The SQL query to retrieve XMPP chat messages.

        Returns:
            List[ArchiveChat]: A list of ArchiveChat instances representing XMPP chat messages.
        """
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
        """
        List XMPP chat messages based on the provided query parameters.

        Args:
            request (Request): The request object containing query parameters.

        Query Parameters:
            timestamp (int): The timestamp in microseconds. If not provided, the current timestamp will be used.
            length (int): The number of messages to retrieve in the response. Default is 50.
            type (str): The type of chat, either "DIRECT" or "CONFERENCE".

        Returns:
            Response: A paginated response containing XMPP chat messages.
        """
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
            return Response({"message": "Invalid Conference Id"}, status=status.HTTP_200_OK)


class NotifyRedirectViewSet(APIView):
    """
    API View to handle notification redirection.

    This view receives notifications and redirects them accordingly. If the notification is for a direct chat,
    it calls the `user_notify_chat` function. If the notification is for a conference chat, it creates a new thread
    and calls the `app_notification` function to handle the notification.

    Request Body Parameters:
        body (str): The content of the message.
        from_user (str): The sender of the message.
        to (str): The recipient of the message.
        xml (str, optional): The XML representation of the message. Defaults to None.
        vhost (str, optional): The virtual host for which the notification is being sent. Defaults to None.

    Returns:
        Response: A response indicating the success of the notification delivery.
    """

    http_method_names = ["post"]
    serializer_class = NotifyRedirectSerializer
    permission_classes = [HasAPIKey]

    def post(self, request):
        message = request.data["body"]
        message_from = request.data["from_user"]
        to = request.data["to"]
        xml = request.data.get("xml")
        vhost = request.data.get("vhost")

        if vhost == settings.XMPP_HOST:
            user_notify_chat(message, message_from, to, xml, vhost)

        elif vhost == "conference" + "." + settings.XMPP_HOST:
            topic_name = request.data.get("to")
            t = threading.Thread(
                target=app_notification,
                args=(topic_name, message_from, message, xml),
            )
            t.start()
        else:
            return Response({"message": "Invalid vhost."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Notification sent."}, status=200)


class MessageAbuseView(APIView):
    """
    API View to handle reporting message abuse.

    This view allows users to report abusive messages by muting receiving messages from another user.
    The view expects a POST request with the necessary information to report the abusive message.

    Request Body Parameters:
        message_ids (str): The IDs of the abusive messages that are being reported.

    Returns:
        Response: A response indicating the success of the reporting process.
    """

    permission_classes = (Authenticate,)
    allowed_methods = ("POST",)
    serializer_class = MessageAbuseSerializer

    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            abuse_mail_msg(serializer.data)
            return Response({"message": "Mail sent Successfully"}, status=200)
        except Exception as exc:
            logger.error(exc)
            logger.exception(exc)
