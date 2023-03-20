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
        key = "%s/circle/${filename}" % request.unique_id
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatImageUploadViewSet(GenericViewSet):
    serializer_class = S3UploadPolicySerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        key = "%s/chat/images/${filename}" % request.unique_id
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatVideoUploadViewSet(GenericViewSet):
    serializer_class = VideoUploadSerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        key = "%s/chat/videos/${filename}" % request.unique_id
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatDocumentsUploadViewSet(GenericViewSet):
    serializer_class = S3UploadPolicySerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        key = "%s/chat/documents/${filename}" % request.unique_id
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())


class ChatAudioUploadViewSet(GenericViewSet):
    serializer_class = S3UploadPolicySerializer
    permission_classes = (Authenticate,)

    def list(self, request):
        key = "%s/chat/audios/${filename}" % request.unique_id
        serializer = self.serializer_class(
            key=key, content_type="image/png/jpeg/jpg/gif"
        )
        return Response(serializer.to_native())
