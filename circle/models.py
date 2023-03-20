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
        return f"ID: {self.id} Name: {self.name}"


class Circle(BaseTimeStampedModel):
    PRIVACY_OPTIONS = [("1", "Public"), ("2", "Private")]
    CIRCLE_TYPES = [("1", "PhoneVerified"), ("2", "Basic"), ("3", "FullyVerified")]
    SUB_CIRCLE_STATUS = [("1", "Approved"), ("2", "Rejected"), ("3", "Pending")]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.URLField(null=True, max_length=255, blank=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    privacy = models.CharField(max_length=5, choices=PRIVACY_OPTIONS, default=2)
    room_id = models.UUIDField(default=uuid.uuid4, editable=False)
    is_purchased = models.BooleanField(default=False)
    branding = models.JSONField(blank=True, null=True)
    is_tenant = models.BooleanField(default=False)
    sites = models.CharField(max_length=200, blank=True, null=True)
    about_me = models.TextField(blank=True)
    circle_type = models.CharField(max_length=5, choices=CIRCLE_TYPES, default=3)
    sub_circle_status = models.CharField(
        max_length=5, choices=SUB_CIRCLE_STATUS, default=1
    )
    hierarchy = models.BooleanField(default=False)
    circle_users_count = models.IntegerField(default=0)
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
        return f"ID: {self.id}, Name: {self.name}"

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
    DEFAULT_ADMIN = 0
    CHIEF_ADMIN = 10
    ADMIN = 20
    MODERATOR = 30
    MEMBER = 40

    name = models.CharField(max_length=255)
    role = models.IntegerField(default=10)
    permissions = models.CharField(max_length=200, blank=True, null=True)

    def set_permissions(self, value):
        self.permissions = json.dumps(value)

    def get_permissions(self):
        return json.loads(self.permissions)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError

        if self.role not in [0, 10, 20, 30, 40]:
            raise ValidationError("Invalid Role")
        else:
            super(CircleRole, self).save(*args, **kwargs)


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


class CirclePermission(BaseTimeStampedModel):
    circle = models.ForeignKey(
        Circle,
        related_name="permissions",
        on_delete=models.CASCADE,
    )
    user_exit = models.BooleanField(default=True)
    pin_message_id = models.CharField(max_length=255, null=True, blank=True)
    pin_message_text = models.CharField(max_length=255, null=True, blank=True)
    link_expired = models.BooleanField(default=False)
    link_expire_time = models.DateTimeField(null=True, blank=True)
    change_circle_info = models.IntegerField(default=20)
    delete_messages = models.IntegerField(default=10)
    ban_users = models.IntegerField(default=10)
    invite_users_via_link = models.IntegerField(default=10)
    pin_new_messages = models.IntegerField(default=30)
    create_sub_circles = models.IntegerField(default=10)
    delete_sub_circles = models.IntegerField(default=10)
    add_delete_other_admins = models.IntegerField(default=10)
    add_delete_moderator = models.IntegerField(default=10)
    add_delete_user = models.IntegerField(default=20)
    assign_moderator_in_sub_circles = models.IntegerField(default=10)
    user_join_permissions = models.IntegerField(default=10)
    post_messages = models.IntegerField(default=40)
    circle_privacy_change = models.IntegerField(default=10)
    change_super_admin = models.IntegerField(default=10)  # TODO: renamed this
    shuffle_circles = models.IntegerField(default=10)
    archive_admin = models.IntegerField(default=10)
    archive_moderator = models.IntegerField(default=10)
    backup_circle = models.IntegerField(default=10)
    mhl = models.IntegerField(default=10)
    filter_members = models.IntegerField(default=10)
    post_level = models.IntegerField(default=0)
    circle_moderation = models.IntegerField(default=0)

    def __str__(self):
        return f"Circle: {self.circle} Permissions"


class CircleInvite(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    sender = models.CharField(max_length=255, null=True, blank=True)
    recipient = models.CharField(max_length=255, null=True, blank=True)
    circle = models.ForeignKey(Circle, related_name="invite", on_delete=models.CASCADE)
    joined = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]
