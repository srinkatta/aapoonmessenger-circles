from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import serializers

from circle.api.utils import get_all_children
from circle.models import (
    AppBranding,
    Circle,
    CircleRole,
    CircleSubscriberRole,
    Customer,
    CustomField,
    SubscriptionPlan,
    Topic,
    CirclePermission,
)


class BaseSerializer(FlexFieldsModelSerializer):
    def create(self, validated_data):
        validated_data["owner_id"] = self.context["request"].user_id
        return super().create(validated_data)


class CircleListSerializer(BaseSerializer):
    level = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    user_exit = serializers.SerializerMethodField()
    change_circle_info = serializers.SerializerMethodField()
    invite_users_via_link = serializers.SerializerMethodField()
    circle_privacy_change = serializers.SerializerMethodField()
    add_delete_user = serializers.SerializerMethodField()
    add_delete_other_admins = serializers.SerializerMethodField()
    add_delete_moderator = serializers.SerializerMethodField()
    create_sub_circles = serializers.SerializerMethodField()
    pin_new_messages = serializers.SerializerMethodField()
    post_messages = serializers.SerializerMethodField()
    circle_moderation = serializers.SerializerMethodField()
    total_count = serializers.SerializerMethodField()

    circle_admins_count = serializers.SerializerMethodField()
    circle_users = serializers.SerializerMethodField()

    archive_admin = serializers.SerializerMethodField()
    archive_moderator = serializers.SerializerMethodField()
    assign_moderator_in_sub_circles = serializers.SerializerMethodField()
    backup_circle = serializers.SerializerMethodField()
    ban_users = serializers.SerializerMethodField()
    delete_messages = serializers.SerializerMethodField()
    delete_sub_circles = serializers.SerializerMethodField()
    filter_members = serializers.SerializerMethodField()
    link_expire_time = serializers.SerializerMethodField()
    link_expired = serializers.SerializerMethodField()
    mhl = serializers.SerializerMethodField()
    pin_message_id = serializers.SerializerMethodField()
    pin_message_text = serializers.SerializerMethodField()
    post_level = serializers.SerializerMethodField()
    shuffle_circles = serializers.SerializerMethodField()
    user_join_permissions = serializers.SerializerMethodField()
    sub_group_status = serializers.SerializerMethodField()
    # topic = serializers.SerializerMethodField()

    class Meta:
        model = Circle
        fields = (
            "created_at",
            "updated_at",
            "total_count",
            "circle_moderation",
            "post_messages",
            "pin_new_messages",
            "create_sub_circles",
            "add_delete_moderator",
            "add_delete_other_admins",
            "add_delete_user",
            "circle_privacy_change",
            "invite_users_via_link",
            "change_circle_info",
            "user_exit",
            "created_by",
            "total_children_count",
            "sub_circle_count",
            "circle_users_count",
            "hierarchy",
            # "max_level",
            "level",
            "hierarchy",
            "hierarchy",
            "id",
            "name",
            "description",
            "image",
            "circle_type",
            # "role",
            "link",
            "room_id",
            "privacy",
            "parent",
            "gensis_circle_id",
        )
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def get_created_by(self, circle):
        return circle.owner_id

    def get_level(self, circle):
        if circle.parent is None:
            return 0
        parents = (
            Circle.objects.filter(pk=circle.parent.pk)
            | circle.parent.get_parent_circles()
        )
        return len(parents)

    def get_total_count(self, circle):
        # total_count = get_all_children(group, include_self=False) | 0
        return 0

    def get_circle_moderation(self, circle):
        permission = circle.permissions.get()
        return permission.circle_moderation

    def get_post_messages(self, circle):
        permission = circle.permissions.get()
        return permission.post_messages

    def get_invite_users_via_link(self, circle):
        permission = circle.permissions.get()
        return permission.invite_users_via_link

    def get_user_exit(self, circle):
        permission = circle.permissions.get()
        return permission.user_exit

    def get_circle_privacy_change(self, circle):
        permission = circle.permissions.get()
        return permission.circle_privacy_change

    def get_add_delete_user(self, circle):
        permission = circle.permissions.get()
        return permission.add_delete_user

    def get_add_delete_other_admins(self, circle):
        permission = circle.permissions.get()
        return permission.add_delete_other_admins

    def get_add_delete_moderator(self, circle):
        permission = circle.permissions.get()
        return permission.add_delete_moderator

    def get_create_sub_circles(self, circle):
        permission = circle.permissions.get()
        return permission.create_sub_circles

    def get_pin_new_messages(self, circle):
        permission = circle.permissions.get()
        return permission.pin_new_messages

    def get_change_circle_info(self, circle):
        permission = circle.permissions.get()
        return permission.change_circle_info


class CircleSerializer(BaseSerializer):
    class Meta:
        model = Circle
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleRoleSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = CircleRole
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleSubscriberRoleSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = CircleSubscriberRole
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CirclePermissionSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = CirclePermission
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class SubscriptionPlanSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CustomerSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = Customer
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class AppBrandingSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = AppBranding
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CustomFieldSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = CustomField
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class TopicSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = Topic
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleHierarchySerializer(FlexFieldsModelSerializer):
    sub_circles = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    gensis_circle_id = serializers.SerializerMethodField()
    max_level = serializers.SerializerMethodField()
    sub_circle_count = serializers.SerializerMethodField()

    class Meta:
        model = Circle
        fields = (
            "id",
            "name",
            "parent",
            "sub_circle_count",
            "level",
            "gensis_circle_id",
            "max_level",
            "sub_circles",
            "room_id",
        )

    def get_sub_circles(self, circle):
        circles = Circle.objects.filter(parent=circle.id)
        serializer = CircleHierarchySerializer(circles, many=True)
        return serializer.data

    def get_sub_circle_count(self, circle):
        circles = Circle.objects.filter(parent=circle.id)
        return circles.count()
