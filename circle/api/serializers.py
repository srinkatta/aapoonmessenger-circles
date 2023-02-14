from urllib.parse import urlparse

from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import serializers

from circle.api.utils import (
    get_all_children,
    get_maximum_level,
    s3_url_extract,
    clear_bucket_from_path,
)
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
    def cloudfront_cdn(self, logo):
        parsed_url = urlparse(logo)
        s3_url = s3_url_extract(logo)
        key = clear_bucket_from_path(parsed_url.path)
        logo = s3_url + key
        return logo

    def validate(self, attrs):
        image = attrs.get("image")
        if image:
            attrs["image"] = self.cloudfront_cdn(image)
        return attrs

    def create(self, validated_data):
        validated_data["owner_id"] = self.context["request"].user_id
        return super().create(validated_data)


class BaseCircleSerializer(BaseSerializer):
    is_owner = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    is_moderator = serializers.SerializerMethodField()
    is_default_admin = serializers.SerializerMethodField()
    is_user = serializers.SerializerMethodField()
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
    # total_count = serializers.SerializerMethodField()

    max_level = serializers.SerializerMethodField()
    circle_admins_count = serializers.SerializerMethodField()
    circle_users_count = serializers.SerializerMethodField()
    sub_circle_count = serializers.SerializerMethodField()
    # circle_users = serializers.SerializerMethodField()
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
    role = serializers.SerializerMethodField()

    class Meta:
        model = Circle
        fields = (
            "created_at",
            "updated_at",
            "id",
            "name",
            "description",
            "image",
            "circle_type",
            "role",
            "link",
            "room_id",
            "privacy",
            "parent",
            # "circle_users",
            "gensis_circle_id",
            # "total_count",
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
            # "total_children_count",
            "sub_circle_count",
            "circle_admins_count",
            "circle_users_count",
            "max_level",
            "level",
            "hierarchy",
            "archive_admin",
            "archive_moderator",
            "assign_moderator_in_sub_circles",
            "backup_circle",
            "ban_users",
            "delete_messages",
            "delete_sub_circles",
            "filter_members",
            "link_expire_time",
            "link_expired",
            "mhl",
            "pin_message_id",
            "pin_message_text",
            "user_join_permissions",
            "post_level",
            "shuffle_circles",
            "topic",
            "sub_circle_status",
            "is_owner",
            "is_admin",
            "is_default_admin",
            "is_moderator",
            "is_user",
        )
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def get_role(self, circle):
        user_id = self.context["request"].user_id
        circle_role = CircleSubscriberRole.objects.filter(
            circle=circle, user_id=user_id
        ).first()
        if circle_role:
            role = circle_role.role.role
            if role == "Default Admin":
                return 0
            if role == "Chief Admin":
                return 10
            if role == "Admin":
                return 20
            if role == "Moderator":
                return 30
            if role == "Member":
                return 40

    def get_is_owner(self, circle):
        user_id = self.context["request"].user_id
        circle_role = CircleSubscriberRole.objects.filter(
            circle=circle, user_id=user_id
        ).first()
        if circle_role and circle_role.role.role == CircleRole.CHIEF_ADMIN:
            return True
        return False

    def get_is_admin(self, circle):
        user_id = self.context["request"].user_id
        circle_role = CircleSubscriberRole.objects.filter(
            circle=circle, user_id=user_id
        ).first()
        if circle_role and circle_role.role.role == CircleRole.ADMIN:
            return True
        return False

    def get_is_default_admin(self, circle):
        user_id = self.context["request"].user_id
        circle_role = CircleSubscriberRole.objects.filter(
            circle=circle, user_id=user_id
        ).first()
        if circle_role and circle_role.role.role == CircleRole.DEFAULT_ADMIN:
            return True
        return False

    def get_is_moderator(self, circle):
        user_id = self.context["request"].user_id
        circle_role = CircleSubscriberRole.objects.filter(
            circle=circle, user_id=user_id
        ).first()
        if circle_role and circle_role.role.role == CircleRole.MODERATOR:
            return True
        return False

    def get_is_user(self, circle):
        user_id = self.context["request"].user_id
        circle_role = CircleSubscriberRole.objects.filter(
            circle=circle, user_id=user_id
        ).first()
        if not circle_role:
            return True
        return False

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
        total_count = get_all_children(circle, include_self=True)
        return total_count.count()

    def get_total_children_count(self, circle):
        total_children_count = get_all_children(circle, include_self=False)
        return total_children_count.count()

    def get_sub_circle_count(self, circle):
        sub_circles = Circle.objects.filter(parent=circle.id)
        return sub_circles.count()

    def get_circle_moderation(self, circle):
        permission = circle.permissions.get()
        return permission.circle_moderation

    def get_circle_users(self, circle):
        circle_role = (
            CircleSubscriberRole.objects.filter(circle=circle)
            .values_list("user_id", flat=True)
            .distinct()
        )
        circle_users = circle_role.exclude(role__role=CircleRole.DEFAULT_ADMIN)
        return circle_users

    def get_max_level(self, circle, count=0):
        return get_maximum_level(circle, count)

    def get_circle_users_count(self, circle):
        circle_users_count = self.get_circle_users(circle)
        return circle_users_count.count()

    def get_circle_admins_count(self, circle):
        circle_admins = (
            CircleSubscriberRole.objects.filter(circle=circle)
            .values_list("user_id", flat=True)
            .distinct()
        )
        admins = circle_admins.exclude(role__name="Moderator")
        return admins.count()

    def get_archive_admin(self, circle):
        permission = circle.permissions.get()
        return permission.archive_admin

    def get_archive_moderator(self, circle):
        permission = circle.permissions.get()
        return permission.archive_moderator

    def get_assign_moderator_in_sub_circles(self, circle):
        permission = circle.permissions.get()
        return permission.assign_moderator_in_sub_circles

    def get_user_join_permissions(self, circle):
        permission = circle.permissions.get()
        return permission.user_join_permissions

    def get_backup_circle(self, circle):
        permission = circle.permissions.get()
        return permission.backup_circle

    def get_ban_users(self, circle):
        permission = circle.permissions.get()
        return permission.ban_users

    def get_delete_messages(self, circle):
        permission = circle.permissions.get()
        return permission.delete_messages

    def get_delete_sub_circles(self, circle):
        permission = circle.permissions.get()
        return permission.delete_sub_circles

    def get_filter_members(self, circle):
        permission = circle.permissions.get()
        return permission.filter_members

    def get_link_expire_time(self, circle):
        permission = circle.permissions.get()
        return permission.link_expire_time

    def get_link_expired(self, circle):
        permission = circle.permissions.get()
        return permission.link_expired

    def get_mhl(self, circle):
        permission = circle.permissions.get()
        return permission.mhl

    def get_pin_message_text(self, circle):
        permission = circle.permissions.get()
        return permission.pin_message_text

    def get_pin_message_id(self, circle):
        permission = circle.permissions.get()
        return permission.pin_message_id

    def get_shuffle_circles(self, circle):
        permission = circle.permissions.get()
        return permission.shuffle_circles

    def get_post_level(self, circle):
        permission = circle.permissions.get()
        return permission.post_level

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


class CircleListSerializer(BaseCircleSerializer):
    class Meta:
        model = Circle
        fields = (
            "id",
            "name",
            "description",
            "image",
            "circle_type",
            "link",
            "room_id",
            "privacy",
            "parent",
            "role",
            "gensis_circle_id",
            "hierarchy",
            "level",
            "user_exit",
            "change_circle_info",
            "invite_users_via_link",
            "circle_privacy_change",
            "add_delete_user",
            "add_delete_other_admins",
            "add_delete_moderator",
            "create_sub_circles",
            "pin_new_messages",
            "post_messages",
            "circle_moderation",
            "sub_circle_count",
            "created_by",
            "circle_users_count",
        )
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleSerializer(BaseCircleSerializer):
    class Meta:
        model = Circle
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleUpdateSerializer(BaseCircleSerializer):
    circle_users = serializers.ListField(required=False)
    user_ids = serializers.ListField(required=False)
    leave = serializers.BooleanField(default=False)

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


class CircleSubscriberRoleInputSerializer(serializers.Serializer):
    circle = serializers.CharField()
    role = serializers.IntegerField()
    user_id = serializers.ListField(required=False)
    connected = serializers.ListField(required=False)

    def validate(self, attrs):
        role = attrs["role"]
        try:
            role = CircleRole.objects.get(role=role)
        except CircleRole.DoesNotExist:
            raise serializers.ValidationError("Role does not exist")
        attrs["role"] = role
        connected = attrs.get("connected", "")
        user_id = attrs.get("user_id", "")

        if not user_id and not connected:
            raise serializers.ValidationError("user_id or connected field is required")
        return attrs

    def create(self, validated_data):
        return CircleSubscriberRole.objects.create(**validated_data)


class CircleSubscriberRoleSerializer(FlexFieldsModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = CircleSubscriberRole
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def get_role(self, instance):
        return instance.role.role


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
    def cloudfront_cdn(self, logo):
        parsed_url = urlparse(logo)
        s3_url = s3_url_extract(logo)
        key = clear_bucket_from_path(parsed_url.path)
        logo = s3_url + key
        return logo

    def validate(self, attrs):
        image = attrs.get("image")
        if image:
            attrs["image"] = self.cloudfront_cdn(image)
        return attrs

    class Meta:
        model = Topic
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
        }


class CircleHierarchySerializer(CircleListSerializer):
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
            "max_level",
            "sub_circles",
            "room_id",
            "privacy",
            "parent",
            "gensis_circle_id",
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
            "sub_circle_count",
            "circle_admins_count",
            "circle_users_count",
            "max_level",
            "level",
            "hierarchy",
            "archive_admin",
            "archive_moderator",
            "assign_moderator_in_sub_circles",
            "backup_circle",
            "ban_users",
            "delete_messages",
            "delete_sub_circles",
            "filter_members",
            "link_expire_time",
            "link_expired",
            "mhl",
            "pin_message_id",
            "pin_message_text",
            "user_join_permissions",
            "post_level",
            "shuffle_circles",
            "topic",
            "sub_circle_status",
        )

    def get_sub_circles(self, circle):
        circles = Circle.objects.filter(parent=circle.id)
        serializer = CircleHierarchySerializer(circles, many=True)
        return serializer.data

    def get_sub_circle_count(self, circle):
        circles = Circle.objects.filter(parent=circle.id)
        return circles.count()

    def get_gensis_circle_id(self, circle):
        if not circle.parent:
            return circle.id
        parents = (
            Circle.objects.filter(pk=circle.parent.pk)
            | circle.parent.get_parent_circles()
        )
        if parents:
            root_parent = parents[0]
            return root_parent.id
        else:
            return circle.id


class HierarchyTransferSerializer(serializers.Serializer):
    to_user = serializers.CharField(required=True)
    circle_id = serializers.CharField(required=True)


class HierarchyDeleteSerializer(serializers.Serializer):
    circle_id = serializers.CharField(required=True)
