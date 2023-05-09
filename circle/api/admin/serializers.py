from rest_framework import serializers
from rest_flex_fields import FlexFieldsModelSerializer

from circle import models as circle_models


class CircleListSerializer(FlexFieldsModelSerializer):
    name = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    circle_users_count = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    hierarchy = serializers.SerializerMethodField()
    total_children_count = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.name

    def get_owner(self, obj):
        return obj.owner_id

    def get_circle_users_count(self, obj):
        return obj.circle_users_count

    def get_created_at(self, obj):
        return obj.created_at

    def get_hierarchy(self, obj):
        return obj.hierarchy

    def get_total_children_count(self, obj):
        return obj.total_children_count

    class Meta:
        model = circle_models.Circle
        fields = [
            "id",
            "name",
            "owner",
            "circle_users_count",
            "created_at",
            "hierarchy",
            "total_children_count",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleDetailSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = circle_models.Circle
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleDefaultConfSerializer(serializers.Serializer):
    """ToDo: Cross check the default details for this serializer cls"""

    max_levels = serializers.IntegerField(default=7)
    max_users = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    circle_type = serializers.SerializerMethodField()
    circle_privacy = serializers.SerializerMethodField()
    change_circle_info = serializers.SerializerMethodField()
    circle_invite_link = serializers.SerializerMethodField()
    circle_privacy_change = serializers.IntegerField(default=10)
    add_remove_admin = serializers.SerializerMethodField()
    add_remove_member = serializers.SerializerMethodField()
    add_remove_moderator = serializers.SerializerMethodField()
    create_sub_circle = serializers.SerializerMethodField()
    pin_new_message = serializers.SerializerMethodField()
    post_messages = serializers.SerializerMethodField()

    def get_max_levels(self, obj):
        return obj.get("max_levels", 7)

    def get_max_users(self, obj):
        return obj.get("max_users", 2560)

    def get_roles(self, obj):
        return obj.get(
            "roles",
            {
                "default_admin": 0,
                "chief_admin": 10,
                "admin": 20,
                "moderator": 30,
                "member": 40,
            },
        )

    def get_circle_type(self, obj):
        return obj.get(
            "circle_type",
            ["PhoneVerified", "Basic", "FullyVerified"],
        )

    def get_circle_privacy(self, obj):
        return obj.get("circle_privacy", ["public", "private"])

    def get_change_circle_info(self, obj):
        return obj.get("change_circle_info", "chief_admin")

    def get_circle_invite_link(self, obj):
        return obj.get("circle_invite_link", "chief_admin")

    def get_add_remove_admin(self, obj):
        return obj.get("add_remove_admin", "chief_admin")

    def get_add_remove_member(self, obj):
        return obj.get("add_remove_member", "admin")

    def get_add_remove_moderator(self, obj):
        return obj.get("add_remove_moderator", "chief_admin")

    def get_create_sub_circle(self, obj):
        return obj.get("create_sub_circle", ["chief_admin", "admin"])

    def get_pin_new_message(self, obj):
        return obj.get("pin_new_message", "moderator")

    def get_post_messages(self, obj):
        return obj.get("post_messages", "member")
