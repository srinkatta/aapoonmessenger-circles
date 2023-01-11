from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import serializers

from circle.models import (
    AppBranding,
    Circle,
    CircleRole,
    CircleSubscriberRole,
    Customer,
    CustomField,
    SubscriptionPlan,
    Topic,
)


class CircleSerializer(FlexFieldsModelSerializer):
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
            "image",
            "post_level",
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
