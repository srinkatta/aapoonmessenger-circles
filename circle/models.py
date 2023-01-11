import json
import uuid

from django.db import models

from common.models import BaseTimeStampedModel


class Topic(BaseTimeStampedModel):
    TOPIC_TYPE = [("1", "Topic"), ("2", "Sub Topic"), ("3", "Sub Sub Topic")]

    name = models.CharField(max_length=255)
    image = models.URLField(null=True, max_length=255, blank=True)
    description = models.TextField(blank=True, null=True)

    parent = models.ForeignKey(
        "self",
        related_name="parent_topic",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    type = models.CharField(max_length=5, choices=TOPIC_TYPE, default=1)

    def __str__(self):
        return self.name


class Circle(BaseTimeStampedModel):
    CIRCLE_TYPES = [("1", "PhoneVerified"), ("2", "Basic"), ("3", "FullyVerified")]
    SUB_CIRCLE_STATUS = [("1", "Approved"), ("2", "Rejected"), ("3", "Pending")]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    room_id = models.UUIDField(default=uuid.uuid4, editable=False)
    is_purchased = models.BooleanField(default=False)
    branding = models.JSONField(blank=True)
    is_tenant = models.BooleanField(default=False)
    sites = models.CharField(max_length=200, blank=True, null=True)
    about_me = models.TextField(blank=True)
    circle_type = models.CharField(max_length=5, choices=CIRCLE_TYPES, default=3)
    sub_circle_status = models.CharField(
        max_length=5, choices=SUB_CIRCLE_STATUS, default=1
    )
    hierarchy = models.BooleanField(default=False)
    group_users_count = models.IntegerField(default=0)
    total_children_count = models.IntegerField(default=0)
    sub_circle_count = models.IntegerField(default=0)
    gensis_circle_id = models.IntegerField(default=0)
    app_id = models.BooleanField(default=False)

    owner_id = models.CharField(max_length=255, null=True, blank=True)

    parent = models.ForeignKey(
        "self",
        related_name="parent_circle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    topic = models.ManyToManyField(Topic, blank=True)

    def __str__(self):
        return f"{self.name}"

    def set_sites(self, value):
        self.sites = json.dumps(value)

    def get_sites(self):
        return json.loads(self.sites)

    def get_parent_circles(self):
        if self.parent is None:
            return Circle.objects.none()
        return (
            Circle.objects.filter(pk=self.parent.pk) | self.parent.get_parent_circles()
        )


class CircleRole(BaseTimeStampedModel):
    name = models.CharField(max_length=255)
    permissions = models.CharField(max_length=200, blank=True, null=True)

    def set_permissions(self, value):
        self.permissions = json.dumps(value)

    def get_permissions(self):
        return json.loads(self.permissions)

    def __str__(self):
        return self.name


class CircleSubscriberRole(BaseTimeStampedModel):
    circle = models.ForeignKey(
        Circle,
        related_name="subscribers",
        on_delete=models.CASCADE,
    )
    role = models.ForeignKey(
        CircleRole,
        related_name="subscribers",
        on_delete=models.CASCADE,
    )
    user_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"User: {self.user_id}, Circle: {self.circle}, Role: {self.role}"


class SubscriptionPlan(BaseTimeStampedModel):
    name = models.CharField(max_length=255)
    price = models.DecimalField(default=0.00, max_digits=10, decimal_places=2)
    storage = models.IntegerField(default=0)
    is_custom_fields_allowed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}, Price: {self.price}"


class Customer(BaseTimeStampedModel):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True, blank=True)
    owner_id = models.CharField(max_length=255, null=True, blank=True)
    app_id = models.CharField(max_length=255, null=True, blank=True)
    plan_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class AppBranding(BaseTimeStampedModel):
    logo = models.CharField(max_length=255, null=True, blank=True)
    header_color = models.CharField(max_length=255, null=True, blank=True)
    background_color = models.CharField(max_length=255, null=True, blank=True)
    foreground_color = models.CharField(max_length=255, null=True, blank=True)
    footer_color = models.CharField(max_length=255, null=True, blank=True)
    customer = models.ForeignKey(
        Customer,
        related_name="app_branding",
        on_delete=models.CASCADE,
    )  # TODO: clear about this as per schema

    def __str__(self):
        return self.customer


class CustomField(BaseTimeStampedModel):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    value = models.CharField(max_length=255)

    circle = models.ForeignKey(
        Circle,
        related_name="custom_fields",
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    ACTIONS = (
        ("like", "like"),
        ("dislike", "dislike"),
        ("forward", "forward"),
        ("reply", "reply"),
    )

    message_id = models.CharField(max_length=100)
    action = models.CharField(choices=ACTIONS, max_length=10)
    action_by = models.CharField(max_length=255, null=True, blank=True)


class MuteCoversation(models.Model):
    """
    Mute Conversation Model
    """

    sender_id = models.CharField(max_length=200)
    recipient_id = models.CharField(max_length=200)
    mute = models.BooleanField(default=False)
    mute_time = models.BigIntegerField(default=0)
