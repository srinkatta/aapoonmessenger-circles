from abc import ABC

from django.db.models import Count, Q
from rest_framework import serializers

from circle.models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    message_id = serializers.CharField(max_length=100)
    like = serializers.SerializerMethodField()
    dislike = serializers.SerializerMethodField()
    forward = serializers.SerializerMethodField()
    reply = serializers.SerializerMethodField()
    action = serializers.ChoiceField(
        required=True, choices=ChatMessage.ACTIONS, write_only=True
    )

    def get_like(self, obj):
        action_data = ChatMessage.objects.filter(message_id=obj.message_id).aggregate(
            like=Count("message_id", filter=Q(action="like"))
        )
        like = action_data["like"]
        return like

    def get_dislike(self, obj):
        action_data = ChatMessage.objects.filter(message_id=obj.message_id).aggregate(
            dislike=Count("message_id", filter=Q(action="dislike"))
        )
        dislike = action_data["dislike"]
        return dislike

    def get_forward(self, obj):
        action_data = ChatMessage.objects.filter(message_id=obj.message_id).aggregate(
            forward=Count("message_id", filter=Q(action="forward"))
        )
        forward = action_data["forward"]
        return forward

    def get_reply(self, obj):
        action_data = ChatMessage.objects.filter(message_id=obj.message_id).aggregate(
            reply=Count("message_id", filter=Q(action="reply"))
        )
        reply = action_data["reply"]
        return reply

    class Meta:
        model = ChatMessage
        fields = "__all__"


class ArchiveChatSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    timestamp = serializers.IntegerField(read_only=True)
    bare_peer = serializers.CharField(max_length=256)
    xml = serializers.CharField(max_length=256)
    username = serializers.CharField(max_length=256)
    user_pic = serializers.URLField(max_length=256)


class NotifyRedirectSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=512)
    xml = serializers.CharField(max_length=256)
    from_user = serializers.CharField(
        max_length=256, label="from", help_text="renamed this `from` to `from_user"
    )
    to = serializers.CharField(max_length=256)
    vhost = serializers.CharField(max_length=256)
    message_id = serializers.CharField(
        max_length=256, allow_null=True, allow_blank=True
    )


class ChatMessageFilterInputSerializer(serializers.Serializer):
    message_id = serializers.ListField()


class ChatMessageFilterSerializer(ChatMessageSerializer):
    class Meta:
        model = ChatMessage
        fields = "__all__"

    def get_like(self, obj):
        action_data = ChatMessage.objects.filter(
            message_id=obj.get("message_id")
        ).aggregate(like=Count("message_id", filter=Q(action="like")))
        like = action_data["like"]
        return like

    def get_dislike(self, obj):
        action_data = ChatMessage.objects.filter(
            message_id=obj.get("message_id")
        ).aggregate(dislike=Count("message_id", filter=Q(action="dislike")))
        dislike = action_data["dislike"]
        return dislike

    def get_forward(self, obj):
        action_data = ChatMessage.objects.filter(
            message_id=obj.get("message_id")
        ).aggregate(forward=Count("message_id", filter=Q(action="forward")))
        forward = action_data["forward"]
        return forward

    def get_reply(self, obj):
        action_data = ChatMessage.objects.filter(
            message_id=obj.get("message_id")
        ).aggregate(reply=Count("message_id", filter=Q(action="reply")))
        reply = action_data["reply"]
        return reply


class MessageAbuseSerializer(serializers.Serializer):
    message_ids = serializers.ListField()
