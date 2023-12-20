import json
import uuid

from django.db import models
from mptt.models import TreeForeignKey, MPTTModel
from common.models import BaseTimeStampedModel


class Topic(BaseTimeStampedModel):
    """
    Topic model represents a topic or sub-topic in your application.

    :param str name: The name of the topic.
    :param str image: The URL of the image related to the topic. (nullable)
    :param str description: The description of the topic. (nullable)
    :param str parent: The parent topic of this topic. (nullable)
    :param str type: The type of the topic. Choices: '1' (Topic), '2' (Sub Topic), '3' (Sub Sub Topic). Default: '1'.
    """

    TOPIC_TYPE = [("1", "Topic"), ("2", "Sub Topic"), ("3", "Sub Sub Topic")]

    name = models.CharField(max_length=255, db_index=True)
    image = models.URLField(null=True, max_length=255, blank=True)
    description = models.TextField(blank=True, null=True)

    parent = models.ForeignKey(
        "self",
        related_name="parent_topic",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=True,
    )
    type = models.CharField(max_length=5, choices=TOPIC_TYPE, default=1, db_index=True)

    def __str__(self):
        return f"ID: {self.id} Name: {self.name}"


class Circle(BaseTimeStampedModel, MPTTModel):
    """
    Circle model represents a community or group of members united by a common interest or purpose.

    :param str name: The name of the circle.
    :param str image: The URL of the image associated with the circle.
    :param str description: A description of the circle.
    :param str link: A link associated with the circle.
    :param str privacy: The privacy setting of the circle. Choices are 'Public' or 'Private'.
    :param UUID room_id: A unique identifier for the circle's room.
    :param bool is_purchased: Whether the circle has been purchased or not.
    :param dict branding: A dictionary containing branding information for the circle.
    :param bool is_tenant: Whether the circle is a tenant or not.
    :param str sites: A string containing information about the circle's associated sites.
    :param str about_me: Additional information or notes about the circle.
    :param str circle_type: The type of the circle. Choices are 'PhoneVerified', 'Basic', or 'FullyVerified'.
    :param str sub_circle_status: The status of sub-circles within this circle. Choices are 'Approved', 'Rejected', or 'Pending'.
    :param bool hierarchy: Whether the circle has a hierarchy or not.
    :param int circle_users_count: The count of users associated with the circle.
    :param int total_children_count: The total count of children circles.
    :param int sub_circle_count: The count of sub-circles within this circle.
    :param int gensis_circle_id: The ID of the genesis circle for this circle.
    :param bool app_id: Whether the circle has an associated app ID or not.

    :param str owner_id: The ID of the circle's owner.

    :param Circle parent: The parent circle of this circle. (ForeignKey relationship)

    :param Topic topic: The topic associated with this circle. (ForeignKey relationship)

    Note: This model inherits from the BaseTimeStampedModel class.
    """

    PRIVACY_OPTIONS = [("1", "Public"), ("2", "Private")]
    CIRCLE_TYPES = [("1", "PhoneVerified"), ("2", "Basic"), ("3", "FullyVerified")]
    SUB_CIRCLE_STATUS = [("1", "Approved"), ("2", "Rejected"), ("3", "Pending")]

    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    image = models.URLField(null=True, max_length=255, blank=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    privacy = models.CharField(max_length=5, choices=PRIVACY_OPTIONS, default=2, db_index=True)
    room_id = models.UUIDField(default=uuid.uuid4, editable=False)
    is_purchased = models.BooleanField(default=False)
    branding = models.JSONField(blank=True, null=True)
    is_tenant = models.BooleanField(default=False)
    sites = models.CharField(max_length=200, blank=True, null=True)
    about_me = models.TextField(blank=True)
    circle_type = models.CharField(max_length=5, choices=CIRCLE_TYPES, default=3, db_index=True)
    sub_circle_status = models.CharField(max_length=5, choices=SUB_CIRCLE_STATUS, default=1)
    hierarchy = models.BooleanField(default=False)
    circle_users_count = models.IntegerField(default=0)
    total_children_count = models.IntegerField(default=0)
    sub_circle_count = models.IntegerField(default=0)
    gensis_circle_id = models.IntegerField(default=0)
    app_id = models.BooleanField(default=False)

    owner_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    parent = TreeForeignKey(
        "self",
        related_name="parent_circle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=True,
    )
    topic = models.ManyToManyField(Topic, blank=True)

    class MPTTMeta:
        order_insertion_by = ["name"]

    def __str__(self):
        return f"ID: {self.id}, Name: {self.name}"

    def set_sites(self, value):
        self.sites = json.dumps(value)

    def get_sites(self):
        return json.loads(self.sites)

    def get_parent_circles(self):
        return self.get_ancestors(include_self=True)

    def get_parent_levels(self, circle, level: int):
        """
        Finds the parent ID of a circle at a specific level within its family.

        Args:
            circle: The current circle.
            level: The target level of the parent.

        Returns:
            The ID of the parent at the specified level, or None if not found.
        """
        circles = circle.get_family()
        for circle in circles:
            if circle.level == level:
                return circle.parent.id if circle.parent else None
        return None


class CircleRole(BaseTimeStampedModel):
    """
    Represents a circle's role model for managing roles and permissions in the circles .

    :param str name: The name of the user.
    :param int role: The role of the user. Possible values are:

        - DEFAULT_ADMIN (0): A default administrative user.
        - CHIEF_ADMIN (10): The chief administrative user with the highest privileges.
        - ADMIN (20): An administrative user with standard privileges.
        - MODERATOR (30): A user with moderator privileges.
        - MEMBER (40): A regular member with basic privileges.

    :param str permissions: Optional. A string representing the user's additional permissions.

    Note: The `role` field should be set to one of the predefined constants above. It determines the level of access
    and permissions the user has within the circles.
    """

    DEFAULT_ADMIN = 0
    CHIEF_ADMIN = 10
    ADMIN = 20
    MODERATOR = 30
    MEMBER = 40

    name = models.CharField(max_length=255, db_index=True)
    role = models.IntegerField(default=10, db_index=True)
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
    """
    Represents the relationship between a Circle and its Subscribers, specifying their roles.

    Attributes:
        circle (Circle): The Circle to which the subscriber belongs.
        role (CircleRole): The role of the subscriber within the Circle.
        user_id (str, optional): An identifier for the subscriber user (can be null/blank).
    """

    """
    CircleSubscriberRole model represents a subscriber's role in a specific Circle within the application.

        :param Circle circle: The Circle to which the subscriber is associated.
        :param CircleRole role: The role of the subscriber within the Circle.
        :param str user_id: The unique identifier of the user who is the subscriber.
    """
    circle = models.ForeignKey(
        Circle,
        related_name="subscribers",
        on_delete=models.CASCADE,
        db_index=True,
    )
    role = models.ForeignKey(
        CircleRole,
        related_name="subscriber_role",
        on_delete=models.CASCADE,
    )
    user_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )

    def __str__(self):
        return f"User: {self.user_id}, Circle: {self.circle}, Role: {self.role}"


class SubscriptionPlan(BaseTimeStampedModel):
    """
    This model represents a subscription plan in the application.

        :param str name: The name of the subscription plan.
        :param Decimal price: The price of the subscription plan.
        :param int storage: The storage limit of the subscription plan.
        :param bool is_custom_fields_allowed: Indicates whether custom fields are allowed for this subscription plan.
    """

    name = models.CharField(max_length=255)
    price = models.DecimalField(default=0.00, max_digits=10, decimal_places=2)
    storage = models.IntegerField(default=0)
    is_custom_fields_allowed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}, Price: {self.price}"


class Customer(BaseTimeStampedModel):
    """
    This class represents a Customer with basic information such as name and address,
    along with optional owner, app, and plan IDs. It inherits from the BaseTimeStampedModel.
    """

    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True, blank=True)
    owner_id = models.CharField(max_length=255, null=True, blank=True)
    app_id = models.CharField(max_length=255, null=True, blank=True)
    plan_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class AppBranding(BaseTimeStampedModel):
    """
    This model allows the customer to customize their app's branding, such as logo and color scheme,
    to create a personalized look and feel for their users
    """

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
    """This model represents a custom field associated with a Circle."""

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
    """
    Represents a chat message with various actions that can be taken on it.

    Parameters:
        message_id (str): The unique identifier for the chat message.
        action (str): The action taken on the message, which can be one of the following: "like", "dislike", "forward", or "reply".
        action_by (str, optional): The user or entity responsible for taking the action on the message.
    """

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
    """
    Model representing the permissions granted to users within a circle.

    Parameters:
        - circle: ForeignKey to the Circle model, the circle to which these permissions belong.
        - user_exit: BooleanField, indicates whether users can exit the circle.
        - pin_message_id: CharField, the ID of the pinned message in the circle, if any.
        - pin_message_text: TextField, the text content of the pinned message, if any.
        - link_expired: BooleanField, indicates if the invite link for the circle has expired.
        - link_expire_time: DateTimeField, the time when the invite link will expire.
        - Various integer fields, representing different permissions levels for different actions:
            - change_circle_info
            - delete_messages
            - ban_users
            - invite_users_via_link
            - pin_new_messages
            - create_sub_circles
            - delete_sub_circles
            - add_delete_other_admins
            - add_delete_moderator
            - add_delete_user
            - assign_moderator_in_sub_circles
            - user_join_permissions
            - post_messages
            - circle_privacy_change
            - change_super_admin (Note: this field may have been renamed)
            - shuffle_circles
            - archive_admin
            - archive_moderator
            - backup_circle
            - mhl
            - filter_members
            - post_level
            - circle_moderation

        Note: The integer fields represent permission levels, with higher values granting more permissions.
    """

    circle = models.ForeignKey(
        Circle,
        related_name="permissions",
        on_delete=models.CASCADE,
        db_index=True,
    )
    user_exit = models.BooleanField(default=False)
    pin_message_id = models.CharField(max_length=255, null=True, blank=True)
    pin_message_text = models.TextField(null=True, blank=True)
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
    """
    Represents a circle invitation instance.

    Attributes:
        created (datetime): The date and time when the invitation was created.
        sender (str, optional): The name of the person who sent the invitation. Can be empty.
        recipient (str, optional): The name of the person who received the invitation. Can be empty.
        circle (Circle): The circle to which the invitation belongs. Represents a foreign key relationship with the Circle model.
        joined (bool): Indicates whether the recipient has joined the circle (True) or not (False).
    """

    created = models.DateTimeField(auto_now_add=True)
    sender = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )
    recipient = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )
    circle = models.ForeignKey(
        Circle,
        related_name="invite",
        on_delete=models.CASCADE,
        db_index=True,
    )
    joined = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]
