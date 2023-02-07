import uuid

from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from circle.api.media_views.s3uploadserializer import (
    S3UploadPolicySerializer,
    VideoUploadSerializer,
)
from circle.middleware.permissions import Authenticate


class GroupImageUploadViewSet(GenericViewSet):
    serializer_class = S3UploadPolicySerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        user_jid = request.jid
        uuid_jid = user_jid.split("@")[0]
        key = "%s/circle/${filename}" % uuid_jid
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatImageUploadViewSet(GenericViewSet):
    serializer_class = S3UploadPolicySerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        user_jid = request.jid
        uuid_jid = user_jid.split("@")[0]
        key = "%s/chat/images/${filename}" % uuid_jid
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatVideoUploadViewSet(GenericViewSet):
    serializer_class = VideoUploadSerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        user_jid = request.jid
        uuid_jid = user_jid.split("@")[0]
        key = "%s/chat/videos/${filename}" % uuid_jid
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatDocumentsUploadViewSet(GenericViewSet):
    serializer_class = S3UploadPolicySerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        user_jid = request.jid
        uuid_jid = user_jid.split("@")[0]
        key = "%s/chat/documents/${filename}" % uuid_jid
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatAudioUploadViewSet(GenericViewSet):
    serializer_class = S3UploadPolicySerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        user_jid = request.jid
        uuid_jid = user_jid.split("@")[0]
        key = "%s/chat/audios/${filename}" % uuid_jid
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())
