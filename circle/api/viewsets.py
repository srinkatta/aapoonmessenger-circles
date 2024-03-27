import re
from typing import Any, Dict, List, Optional, Set

import phonenumbers
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.models.functions import Lower
from drf_spectacular.utils import OpenApiParameter, extend_schema
from loguru import logger
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from circle.api import service as circle_service
from circle.api.mixins import BulkCreateCircleInviteMixin
from circle.api.serializers import (
    AppBrandingSerializer,
    AssignUserRoomTopicSerializer,
    CircleDetailsSerializer,
    CircleHierarchySerializer,
    CircleHierarchySerializerV2,
    CircleInputSerializer,
    CircleInviteAcceptSerializer,
    CircleInviteCreateSerializer,
    CircleInviteResponseSerializer,
    CircleInviteSerializer,
    CircleInviteUpdateSerializer,
    CircleLeaveSerializer,
    CircleLevelNameConfigSerializer,
    CircleListSerializer,
    CirclePermissionSerializer,
    CircleReportSerializer,
    CircleRoleSerializer,
    CircleSerializer,
    CircleSubscribedUsersSerializer,
    CircleSubscriberRoleInputSerializer,
    CircleSubscriberRoleSerializer,
    CircleUpdateSerializer,
    CustomerSerializer,
    CustomFieldSerializer,
    HierarchyDeleteSerializer,
    HierarchyTransferSerializer,
    SubscriptionPlanSerializer,
    TopicSerializer,
    UserCategorySerializer,
)
from circle.api.utils import (
    CircleInvitePagination,
    GenericPagination,
    circle_properties_update,
    get_admin_circles,
    get_all_children,
    get_chief_admin_leaf_circles,
    get_circle_by_id,
    get_gensis_circle_id,
    get_hierarchy_status,
    get_level,
    get_top_level_circles,
    logged_user_info,
    update_parent_hierarchy,
    circle_version_increment,
)
from circle.helpers.ejjaberd import (
    create_xmpp_room,
    destroy_room,
    member_subscribe_topic,
    member_xmpp_room_subscribe,
    member_xmpp_room_unsubscribe,
)
from circle.middleware.permissions import Authenticate
from circle.models import (
    AppBranding,
    Circle,
    CircleInvite,
    CircleLevelNameConfig,
    CirclePermission,
    CircleRole,
    CircleSubscriberRole,
    Customer,
    CustomField,
    SubscriptionPlan,
    Topic,
)
from circle.services.user import User

ERROR_MESSAGE = "Sorry, We are  facing an issue currently. Thanks for noticing . We fix it soon."


class BaseCircleViewSet(viewsets.ModelViewSet):
    """
    This is a base ViewSet for all objects directly related to circle.

    Properties:
    - circle_id: A property that retrieves the 'circle_id' from the view's kwargs.

    Methods:
    - get_circle: Retrieves and returns the Circle object with the specified 'circle_id'.
    - get_circle_by_id(pk): Retrieves and returns the Circle object with the specified primary key 'pk'.
    - get_serializer_context(): Overrides the method from the parent class to include additional context data for serializers.
        - circle_id: The 'circle_id' extracted from the view's kwargs.
        - request: The current request object.

    Note:
    - This base ViewSet is intended to be inherited by other ViewSets for insurance claim-related objects.
    - It provides common functionality for handling circles and sets up the serializer context.
    """

    @property
    def circle_id(self):
        """
        Property to retrieve the 'circle_id' from the view's kwargs.

        Returns:
        - int or None: The 'circle_id' if found in kwargs, otherwise None.
        """
        circle_id = self.kwargs.get("circle_id")
        return circle_id

    def get_circle(self):
        """
        Retrieve the Circle object with the specified 'circle_id'.

        Returns:
        - Circle: The Circle object matching the 'circle_id'.

        Raises:
        - Http404: If no Circle object is found with the specified 'circle_id'.
        """
        return get_object_or_404(Circle.objects.all(), id=self.circle_id)

    def get_circle_by_id(self, pk):
        """
        Retrieve the Circle object with the specified primary key 'pk'.

        Args:
        - pk (int): The primary key of the Circle object.

        Returns:
        - Circle: The Circle object matching the primary key 'pk'.

        Raises:
        - Http404: If no Circle object is found with the specified primary key 'pk'.
        """
        return get_object_or_404(Circle, id=pk)

    def get_serializer_context(self):
        """
        Overrides the method from the parent class to include additional context data for serializers.

        Returns:
        - dict: The serializer context containing the following data:
            - 'circle_id': The 'circle_id' extracted from the view's kwargs.
            - 'request': The current request object.
        """
        context = super().get_serializer_context()
        context["circle_id"] = self.kwargs.get("circle_id")
        context["request"] = self.request
        return context


class CircleViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update, and delete circles.

    Attributes:
        serializer_class (CircleSerializer): The serializer class used for the circle data.
        permission_classes (tuple): The permission classes to control access to the viewset.
        pagination_class (GenericPagination): The pagination class for handling paginated responses.

    """

    serializer_class = CircleSerializer
    permission_classes = (Authenticate,)
    pagination_class = GenericPagination

    def get_serializer_class(self):
        """
        Returns the appropriate serializer class based on the request method.

        Returns:
           Serializer class: The serializer class to be used for the current request.
        """
        if self.request.method == "GET":
            return CircleListSerializer
        elif self.request.method in ["POST", "PUT", "PATCH"]:
            return CircleInputSerializer
        else:
            return CircleSerializer

    def get_queryset(self):
        """
        Returns the queryset of circles filtered by the requesting user's owner_id.

        Returns:
            queryset: Filtered queryset of Circle objects based on owner_id.
        """
        queryset = Circle.objects.filter(owner_id=self.request.user_id)
        return queryset

    def hierarchy_limit(self, parent_id):
        """
        Checks if the circle hierarchy level exceeds the limit of 7.

        Args:
            parent_id (int): The ID of the parent circle.

        Returns:
            bool: True if the hierarchy level exceeds 7, False otherwise.
        """
        parent_circle = Circle.objects.get(id=parent_id)
        parents = get_level(parent_circle)
        return parents >= 7

    def create_parent_circle_status(self, circle, user, data):
        """
        Creates a parent circle with the provided data, considering the user's admin status.

        If the user is in the admin_list, the subgroup_status will be set to "1".
        Otherwise, it will be set to "3".

        Args:
            circle (Circle): The circle instance for which the parent circle is being created.
            user (User): The user instance whose admin status is checked.
            data (dict): The data for creating the parent circle.

        Returns:
            None
        """
        admin_list = (
            CircleSubscriberRole.objects.filter(circle=circle)
            .values_list("user_id", flat=True)
            .distinct()
        )

        if user in admin_list:
            data["subgroup_status"] = "1"
            self.create_parent_circle(**data)
        else:
            data["subgroup_status"] = "3"
            self.create_parent_circle(**data)

    def circle_add_default_admins(self, circle, parent):
        """
        Adds default administrators to the given circle based on the parent circle.

        Default administrators are users who have the 'DEFAULT_ADMIN' or 'CHIEF_ADMIN' role in the parent circle.

        Args:
            circle (Circle): The circle to which the default administrators will be added.
            parent (Circle): The parent circle from which the default administrators will be retrieved.

        Returns:
            None
        """
        default_admin = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
        chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
        default_admins = CircleSubscriberRole.objects.filter(
            role=default_admin, circle=parent
        ).values_list("user_id", flat=True)
        chief_admins = CircleSubscriberRole.objects.filter(
            role=chief_admin, circle=parent
        ).values_list("user_id", flat=True)
        admins = default_admins | chief_admins

        for admin in admins:
            if not CircleSubscriberRole.objects.filter(user_id=admin, circle=circle):
                role = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
                user_service = User()
                user = user_service.details(user_id=admin)
                if not user:
                    logger.info(f"Moving to next admin")
                    logger.error(f"No User exists with the given user_id: {admin}")
                else:
                    # Adding all hidden/default admins to circle and xmpp_room
                    circle_service.circle_add_user(
                        circle,
                        user,
                        role=role,
                    )

    def circle_add_parent_default_admins(self, parent: Circle, user):
        """
        Adds default administrators to all child circles of the given parent circle.

        Default administrators are users who have the 'CHIEF_ADMIN' role in the parent circle.

        Args:
            parent (Circle): The parent circle for which child circles will be processed.
            user (dict): The user information used to fetch user details.

        Returns:
            None
        """
        user_service = User()
        user = user_service.details(user_id=user["id"])

        if not user:
            logger.info(f"Moving to next admin")
            logger.error(f"No User exists with the given user_id")
        else:
            parent_circles = parent.get_parent_circles()
            for circle in parent_circles:
                role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
                super_admins = CircleSubscriberRole.objects.filter(
                    role=role, circle=circle
                ).values_list("user_id", flat=True)

                if not super_admins:
                    for admin in super_admins:
                        user_service = User()
                        user = user_service.details(user_id=admin)
                        if not user:
                            logger.info(f"Moving to next admin")
                            logger.error(f"No User exists with the given user_id: {admin}")
                        else:
                            role = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
                            circle_service.circle_add_user(circle, user, role=role)

    def circle_add_topics(self, circle, topic):
        if topic:
            topics = Topic.objects.filter(id=topic[0].id)
            for topic in topics:
                circle.topic.add(topic)

    def get_circle_with_level(self, circles):
        """
        Groups circles based on their hierarchy level.

        Given a list of circles, this method groups them into a dictionary where the key is the hierarchy level,
        and the value is a list of circles at that level.

        Args:
            circles (list): A list of Circle objects to be grouped.

        Returns:
            dict: A dictionary with hierarchy level as key and a list of circles at that level as value.
        """
        circles_with_level = {}
        for circle in circles:
            level = get_level(circle)
            try:
                circles_with_level[level].append(circle)
            except KeyError:
                circles_with_level[level] = [circle]
        return circles_with_level

    def remove_users_from_circle(self, circle, user_ids: List):
        """
        Remove users from a circle only if there are associated users in the circle.

        Given a circle and a list of user_ids, this method removes those users from the circle
        only if the circle has at least one associated user.

        Args:
            circle (Circle): The circle from which users will be removed.
            user_ids (List): A list of user_ids to be removed from the circle.

        Returns:
            None
        """
        circle_users = CircleSubscriberRole.objects.filter(circle=circle).count()
        if circle_users >= 1:
            CircleSubscriberRole.objects.filter(user_id__in=user_ids, circle=circle).delete()
            for user in user_ids:
                # delete invitation from circle
                CircleInvite.objects.filter(
                    Q(sender=user) | Q(recipient=user),
                    circle=circle,
                ).delete()
                user_service = User()
                logger.info(f"user_id: {user}")
                user = user_service.details(user_id=user)
                if not user:
                    logger.info(f"Moving to next admin")
                    logger.error(f"No User exists with the given user_id")
                else:
                    member_xmpp_room_unsubscribe(user["jid"], circle.room_id)
                    # member_unsubcribe_topic(tokens=[user.get("fcm_token")], topic=circle.room_id)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="privacy",
                description="Filter by privacy of circle",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="name",
                description="Filter by name of circle",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="site",
                description="Filter Web-based circles",
                required=False,
                type=str,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """
        List circles based on provided query parameters.

        If the 'privacy' parameter is provided in the request query, the method filters circles based on the privacy value
        and optionally on the 'name' parameter as well.

        If the 'name' parameter is provided in the request query, the method performs a circle name search.

        If no query parameters are provided, the method fetches circles to which the requesting user is subscribed.

        Args:
            request (HttpRequest): The request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A paginated response containing serialized circle data.
        """
        if "privacy" in request.GET:
            privacy = request.GET.get("privacy", "")
            name = request.GET.get("name", "")
            circles = self.filter_circles_privacy(privacy, name)

        elif "name" in request.GET:
            circles = self.circle_name_search(request)

        elif "site" in request.GET:
            print("**Triggered Web based circles**")
            chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
            default_admin = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
            circle_ids = []

            # Single query optimizes circle data & role fetching
            final_circles = (
                CircleSubscriberRole.objects.select_related("subscribers")
                .filter(user_id=request.user_id)
                .exclude(role=chief_admin, circle__parent__isnull=False)
                .exclude(role=default_admin)
                .values_list("circle__id", flat=True)
            )
            circle_ids.extend(final_circles)
            print("**Retrieved final circles from database (optimized).**")

            # Fetch cheif admins main/genesis circles within the hierarchy
            subscribed_circle_ids = (
                CircleSubscriberRole.objects.select_related("subscribers")
                .filter(
                    user_id=request.user_id,
                    role=chief_admin,
                    circle__parent=None,
                    circle__total_children_count__gte=1,
                )
                .values_list("circle_id", flat=True)
            )
            circle_ids.extend(subscribed_circle_ids)

            # Fetch top level circles within the chief admins hierarchy
            top_level_circle_ids: Set[int] = get_top_level_circles(
                user_id=request.user_id,
                chief_admin=chief_admin,
                subscribed_circle_ids=subscribed_circle_ids,
            )
            circle_ids.extend(top_level_circle_ids)

            # Retrieve sub-circles owned by the root circle's admin
            admin_circle: List[int] = get_admin_circles(
                user_id=request.user_id, chief_admin=chief_admin
            )
            circle_ids.extend(admin_circle)

            circles = Circle.objects.select_related("parent").filter(id__in=circle_ids)

        else:
            print("**Triggered all circles list**")
            final_circles = (
                CircleSubscriberRole.objects.select_related("circle")
                .select_related("role")
                .filter(user_id=request.user_id)
                .values_list("circle__id", flat=True)
            )
            print("**Retrieved final circles from database.**")

            circles = (
                Circle.objects.select_related("parent")
                .prefetch_related("topic")
                .filter(id__in=final_circles)
            )
            print("**Filtered circles based on validation criteria.**")

        queryset = circles.order_by("-id")
        page = self.paginate_queryset(queryset)

        serializer = self.get_serializer_class()(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    def filter_circle_privacy_name(self, queryset, name):
        """
        Filter the queryset based on the circle name.

        This function filters the queryset by performing a case-insensitive search for the provided 'name'.

        Args:
            queryset (QuerySet): The queryset to be filtered.
            name (str): The name of the circle to be searched.

        Returns:
            QuerySet: The filtered queryset based on the 'name'.
        """
        if name:
            name = name.lower()
            qs = queryset.annotate(name_lower=Lower("name"))
            final_groups = qs.filter(name_lower__icontains=name)
            queryset = final_groups.order_by("name")
            return queryset
        else:
            return queryset

    def filter_circles_privacy(self, privacy, name):
        """
        Filter circles based on privacy and name.

        This method filters circles based on the provided 'privacy' and 'name' parameters.

        Args:
            privacy (str): The privacy value for filtering circles (either 'public' or 'private').
            name (str): The name of the circle to be searched.

        Returns:
            QuerySet: The filtered queryset of circles.
        """
        if privacy in ["public", "Public", "1", 1]:
            privacy = 1

            queryset = (
                Circle.objects.select_related("parent")
                .prefetch_related("topic")
                .filter(privacy=privacy)
                .exclude(owner_id=self.request.user_id)
            )
            results = self.filter_circle_privacy_name(queryset, name)
            return results

        if privacy in ["private", "private", "2", 2]:
            privacy = 2
            queryset = (
                Circle.objects.select_related("parent")
                .prefetch_related("topic")
                .filter(privacy=privacy)
                .exclude(owner_id=self.request.user_id)
            )
            results = self.filter_circle_privacy_name(queryset, name)
            return results

    def circle_name_search(self, request):
        """
        Search for circles based on the provided 'name'.

        This method performs a case-insensitive search for circles with names containing the specified 'name' parameter.

        Args:
            request (HttpRequest): The request object containing the 'name' parameter.

        Returns:
            QuerySet: The filtered queryset of circles matching the search criteria.
        """
        name = request.GET["name"]
        name = name.lower()
        final_circles = (
            CircleSubscriberRole.objects.select_related("circle")
            .filter(user_id=request.user_id)
            .values_list("circle__id", flat=True)
        )

        circles = Circle.objects.filter(id__in=final_circles)
        qs = circles.annotate(name_lower=Lower("name"))
        circles = qs.filter(name_lower__icontains=name)
        return circles

    def create(self, request, *args, **kwargs):
        """
        Create a new circle based on the provided data.

        This method handles the creation of a new circle using the data provided in the request.
        If a 'parent' circle is specified, the new circle will be created as a child of the parent circle.
        If no 'parent' is provided, the new circle will be created as a top-level circle.

        Args:
            request (HttpRequest): The request object containing the circle data.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response containing the serialized data of the created circle.
        """
        import sys

        python_version = sys.version  # Todo remove after python version verify
        logger.info(f"Python Version from logger: {python_version}")
        serializer = self.get_serializer(data=request.data, context={"request": request})
        if request.data.get("parent"):
            parent_circle = serializer.initial_data["parent"]
            try:
                Circle.objects.get(id=parent_circle)
            except Circle.DoesNotExist as exc:
                return Response(
                    {
                        "detail": f"{exc}",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get("parent")
        topic = serializer.validated_data.get("topic")
        if parent:
            # Child circle limit
            limit = self.hierarchy_limit(parent.id)
            if limit:
                return Response(
                    {"detail": "You reached the maximum limit of 8 child circles."},
                    status=400,
                )

            circle = serializer.save()

            # Create XMPP Room
            create_xmpp_room(circle)

            # Get or create root circle level-name configuration instance
            root_circle = circle.get_root()
            level_config, created = CircleLevelNameConfig.objects.get_or_create(circle=root_circle)

            self.circle_add_topics(circle, topic)

            # Add Owner to circle and add to xmpp_room
            role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
            user_info = logged_user_info(request)
            circle_service.circle_add_user(circle, user_info, role)

            # Add default admins to circle and xmpp_room
            self.circle_add_default_admins(circle, parent)

            # Adding all admins of parent groups as default admin of this circle
            self.circle_add_parent_default_admins(parent, user_info)

        else:
            circle = serializer.save()

            # Create XMPP Room
            create_xmpp_room(circle)

            self.circle_add_topics(circle, topic)

            # Add Owner to circle and add to xmpp_room
            role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
            user_info = logged_user_info(request)
            circle_service.circle_add_user(circle, user_info, role)
        serializer = CircleSerializer(circle, context={"request": request})

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve details of a specific circle.

        This method retrieves the details of a specific circle based on the provided circle ID (pk).
        If the circle with the given ID does not exist, a 400 Bad Request response is returned.

        Args:
            request (HttpRequest): The request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response containing the serialized data of the retrieved circle.
        """
        try:
            circle = self.get_circle_by_id(kwargs.get("pk"))
        except Circle.DoesNotExist:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CircleSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """
        Update details of a specific circle.

        This method updates the details of a specific circle based on the provided circle ID (pk).
        If the circle with the given ID does not exist, a 400 Bad Request response is returned.
        The circle is updated with the data provided in the request.

        Add or update users to the circle.
        Remove or delete users from a circle

        Args:
            request (HttpRequest): The request object containing the updated circle data.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response containing the serialized data of the updated circle.
        """

        try:
            circle = self.get_circle_by_id(kwargs.get("pk"))
        except Circle.DoesNotExist:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CircleUpdateSerializer(circle, context={"request": request}, data=request.data)
        serializer.is_valid(raise_exception=True)
        circle_serializer = serializer.save()

        # Add or Update user circle
        circle_users = serializer.validated_data.get("circle_users")
        if circle_users:
            user_service = User()
            for circle_user in circle_users:
                role = circle_user.get("role")
                connected = circle_user.get("connected")
                user = user_service.get_details_from_phone(phone_number=connected)

                if not user:
                    logger.error(f"No User exists with the given phone_number: {connected}")
                    logger.info(f"Moving on to the next user")
                else:
                    try:
                        circle_service.validate_circle_add_user(request, user, role, circle)
                        logger.info("Adding new user to circle")
                        role = CircleRole.objects.get(role=role)
                        circle_service.circle_add_user(circle, user, role=role)
                    except CircleRole.DoesNotExist as exc:
                        logger.error("Error while adding new user to circle")
                        logger.exception(exc)
                    except Exception as exc:
                        logger.error("Error while adding new user to circle")
                        logger.exception(exc)

        # Delete User:
        leave = serializer.validated_data.get("leave")
        user_ids = serializer.validated_data.get("user_ids")
        if leave and user_ids:
            self.remove_users_from_circle(circle, user_ids)
        serializer = CircleSerializer(circle_serializer, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None, *args, **kwargs):
        """
        Delete a specific circle.

        This method deletes a specific circle based on the provided circle ID (pk).
        If the circle with the given ID does not exist, a 400 Bad Request response is returned.

        Args:
            request (HttpRequest): The request object.
            pk (int): The primary key of the circle to be deleted.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response indicating the success of the circle deletion.
        """
        parent = None
        try:
            circle = Circle.objects.get(id=pk)
            room_id = circle.room_id
            if circle.parent:
                parent = circle.parent
        except Circle.DoesNotExist:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        circle.delete()
        destroy_room(room_id)
        if parent:
            update_parent_hierarchy(parent)
        return Response({"message": "Circle Deleted Successfully"}, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="level",
                description="Filter by level of circle",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="name",
                description="Filter by name of circle",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="parent",
                description="Filter by parent id of circle",
                required=False,
                type=int,
            ),
            OpenApiParameter(
                name="university",
                description="Filter by university",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="college",
                description="Filter by college",
                required=False,
                type=str,
            ),
        ]
    )
    @action(
        detail=True,
        methods=["GET"],
        permission_classes=[],
    )
    def hierarchy(self, request, pk=None):
        """
        Retrieve the hierarchy of circles based on the provided circle ID.

        This method retrieves the hierarchy of circles based on the provided circle ID (pk).
        The circles can be filtered by 'level', 'name', or 'parent' ID using the request query parameters.

        Args:
            request (HttpRequest): The request object containing the query parameters for filtering circles.
            pk (int): The primary key of the circle from which the hierarchy will be retrieved.

        Returns:
            Response: A paginated response containing the serialized data of the circles in the hierarchy.
        """
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response(
                {"detail": "Circle does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        circles = self.filter_circles(request, circle)
        page = self.paginate_queryset(circles)
        serializer = CircleListSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    def filter_circles(self, request, circle):
        """
        Filter circles based on the provided query parameters.

        This method filters circles based on the query parameters provided in the request.
        The circles can be filtered by 'name', 'level', and 'parent' ID using the request query parameters.

        Args:
            request (HttpRequest): The request object containing the query parameters for filtering circles.
            circle (Circle): The circle from which the filtering will be applied.

        Returns:
            list: A list of Circle objects filtered based on the provided query parameters.
        """
        if "name" in request.GET and "level" not in request.GET:
            return circle_service.filter_circles_by_name(request, circle)
        elif "level" in request.GET and "name" not in request.GET and "parent" not in request.GET:
            return circle_service.filter_circles_by_level(request, circle)
        elif "level" in request.GET and "name" in request.GET and "parent" not in request.GET:
            return circle_service.filter_circles_by_name_and_level(request, circle)
        elif "level" in request.GET and "parent" in request.GET and "name" not in request.GET:
            return circle_service.filter_circles_by_parent(request, circle)
        else:
            return [circle]

    @action(
        detail=True,
        methods=["GET"],
    )
    def link(self, request, pk=None):
        """
        Retrieve details of a specific circle using the circle link.

        This method retrieves the details of a specific circle based on the provided circle link (pk).
        If the circle with the given link does not exist, a 400 Bad Request response is returned.

        Args:
            request (HttpRequest): The request object.
            pk (str): The circle link.

        Returns:
            Response: A response containing the serialized data of the retrieved circle.
        """
        try:
            circle = Circle.objects.get(link=pk)
        except Exception:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CircleSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
    )
    def info(self, request, pk=None):
        """
        Retrieve details of a specific circle.

        This method retrieves the details of a specific circle based on the provided circle ID (pk).
        If the circle with the given ID does not exist, a 400 Bad Request response is returned.

        Args:
            request (HttpRequest): The request object.
            pk (int): The primary key of the circle to be retrieved.

        Returns:
            Response: A response containing the serialized data of the retrieved circle.
        """
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CircleSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="role",
                description="Filter by role",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="name",
                description="Filter by name",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="phone",
                description="Filter by phone",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="university",
                description="Filter by university",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="college",
                description="Filter by college",
                required=False,
                type=str,
            ),
        ]
    )
    @action(
        detail=True,
        methods=["GET"],
    )
    def users(self, request, pk=None):
        """
        Retrieve users associated with a specific circle.

        This method retrieves the users associated with a specific circle based on the provided circle ID (pk).
        The users can be filtered by 'role' and 'name' using the request query parameters.

        Args:
            request (HttpRequest): The request object containing the query parameters for filtering users.
            pk (int): The primary key of the circle from which users will be retrieved.

        Returns:
            Response: A paginated response containing the serialized data of the users associated with the circle.
        """
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)

        role = request.GET.get("role", None)
        name = request.GET.get("name", None)
        phone = request.GET.get("phone", None)
        university = request.GET.get("university", None)
        college = request.GET.get("college", None)

        if role == "admins":
            role = [10, 20]
            circle_users = CircleSubscriberRole.objects.filter(circle=circle, role__role__in=role)
        elif role:
            circle_users = CircleSubscriberRole.objects.filter(circle=circle, role__role=role)
        else:
            circle_users = CircleSubscriberRole.objects.filter(circle=circle)

        circle_users = circle_users.order_by("-id")
        page = self.paginate_queryset(circle_users)
        serializer = CircleSubscribedUsersSerializer(page, many=True, context={"request": request})

        if name:
            circle_users = self.filter_circle_subscribed_users(serializer.data, "user_name", name)
            page = self.paginate_queryset(circle_users)
            serializer = CircleSubscribedUsersSerializer(
                page, many=True, context={"request": request}
            )
        if phone:
            circle_users = self.filter_circle_subscribed_users(serializer.data, "user_phone", phone)
            page = self.paginate_queryset(circle_users)
            serializer = CircleSubscribedUsersSerializer(
                page, many=True, context={"request": request}
            )
        if university:
            circle_users = self.filter_circle_subscribed_users(
                serializer.data, "university", university
            )
            page = self.paginate_queryset(circle_users)
            serializer = CircleSubscribedUsersSerializer(
                page, many=True, context={"request": request}
            )
        if college:
            circle_users = self.filter_circle_subscribed_users(serializer.data, "college", college)
            page = self.paginate_queryset(circle_users)
            serializer = CircleSubscribedUsersSerializer(
                page, many=True, context={"request": request}
            )

        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["PUT"],
        url_path="delete/members",
        serializer_class=CircleLeaveSerializer,
    )
    def delete_members(self, request, pk=None):
        """
        Remove/unsubscribe users from a circle.

        This method removes or unsubscribes users from a circle based on the provided circle ID (pk).
        The users to be removed/unsubscribed are specified in the request payload using the 'user_ids' field.

        Args:
            request (HttpRequest): The request object containing the circle leave data.
            pk (int): The primary key of the circle from which users will be removed/unsubscribed.

        Returns:
            Response: A response indicating the success of the user removal/unsubscription.
        """
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CircleLeaveSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data.get("user_ids")
        if user_ids:
            self.remove_users_from_circle(circle, user_ids)
        serializer = CircleSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="role",
                description="Filter by role",
                required=False,
                type=str,
            ),
        ]
    )
    @action(detail=False, methods=["GET"], url_path="role")
    def get_circle_by_role(self, request):
        """
        Retrieve associated circles based on the user's role.

        This method returns the associated circles based on the user's role specified in the request query parameters.
        The user's role is provided using the 'role' parameter in the request.

        Args:
            request (HttpRequest): The request object containing the user's role.

        Returns:
            Response: A paginated response containing the serialized data of the associated circles.
        """
        user_id = request.user_id
        role = request.GET.get("role", "")
        circle_ids = []
        chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
        if role == "myorg":
            # Fetch cheif admins main/genesis circles within the hierarchy
            subscribed_circle_ids = (
                CircleSubscriberRole.objects.select_related("subscribers")
                .filter(
                    user_id=user_id,
                    role=chief_admin,
                    circle__parent=None,
                    circle__total_children_count__gte=1,
                )
                .values_list("circle_id", flat=True)
            )
            circle_ids.extend(subscribed_circle_ids)

            # Fetch top level circles within the chief admins hierarchy
            top_level_circle_ids: Set[int] = get_top_level_circles(
                user_id=user_id,
                chief_admin=chief_admin,
                subscribed_circle_ids=subscribed_circle_ids,
            )
            circle_ids.extend(top_level_circle_ids)

            # Retrieve sub-circles owned by the root circle's admin
            admin_circle: List[int] = get_admin_circles(user_id=user_id, chief_admin=chief_admin)
            circle_ids.extend(admin_circle)

        elif int(role) == CircleRole.CHIEF_ADMIN:
            # Fetch single circles of cheif admin
            subscribed_circle_ids = (
                CircleSubscriberRole.objects.select_related("subscribers")
                .filter(
                    user_id=user_id,
                    role=chief_admin,
                    circle__parent=None,
                    circle__sub_circle_count=0,
                )
                .values_list("circle_id", flat=True)
            )
            circle_ids.extend(subscribed_circle_ids)

            # Retrieve chief admin circles with no sub-circles, excluding cases where the
            # user holds chief admin role in the root circle and parent circle.
            chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
            circles = get_chief_admin_leaf_circles(request.user_id, chief_admin)
            circle_ids.extend(circles)

        elif int(role) in [
            CircleRole.ADMIN,
            CircleRole.DEFAULT_ADMIN,
            CircleRole.MODERATOR,
            CircleRole.MEMBER,
        ]:
            # Fetch circles based on role
            subscribed_circle_ids = (
                CircleSubscriberRole.objects.select_related("subscribers")
                .filter(user_id=user_id, role__role=role)
                .values_list("circle_id", flat=True)
            )
            circle_ids.extend(subscribed_circle_ids)

        circles = Circle.objects.select_related("parent").filter(id__in=circle_ids).order_by("-id")
        page = self.paginate_queryset(circles)
        serializer = CircleListSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    def filter_circle_subscribed_users(self, serializer_data, attribute, value):
        user_ids = []

        for user_details in serializer_data:
            if user_details.get(attribute) and value.lower() in user_details.get(attribute).lower():
                user_ids.append(user_details["id"])

        circle_users = CircleSubscriberRole.objects.filter(id__in=user_ids)
        return circle_users


class CircleRoleViewSet(BaseCircleViewSet):
    """
    Viewset to manage circle roles.

    This viewset provides endpoints to perform CRUD (Create, Read, Update, Delete) operations on circle roles.
    Circle roles define different roles or permissions that users can have within a circle.

    Attributes:
        serializer_class: The serializer class to use for serializing and deserializing circle role data.
        permission_classes: The permission classes to use for controlling access to the viewset.

    Methods:
        get_queryset: Get the queryset for retrieving all circle roles.
    """

    serializer_class = CircleRoleSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        """
        Get the queryset for retrieving all circle roles.

        This method retrieves all circle roles available in the database.

        Returns:
            QuerySet: The queryset containing all circle roles.
        """
        return CircleRole.objects.all()


class CirclePermissionViewSet(BaseCircleViewSet):
    """
    Viewset to manage circle permissions.

    This viewset provides endpoints to perform CRUD (Create, Read, Update, Delete) operations on circle permissions.
    Circle permissions define the permissions or access rights that users have within a circle.

    Attributes:
        serializer_class: The serializer class to use for serializing and deserializing circle permission data.
        permission_classes: The permission classes to use for controlling access to the viewset.
        http_method_names: The allowed HTTP methods for this viewset.

    Methods:
        get_queryset: Get the queryset for retrieving circle permissions.

        list: List the circle permissions for the current circle.
        create/update: Create/Update a circle permission.
    """

    serializer_class = CirclePermissionSerializer
    permission_classes = (Authenticate,)
    http_method_names = ("get", "post")

    def get_queryset(self):
        """
        Get the queryset for retrieving circle permissions.

        This method retrieves the circle permissions associated with the current circle.

        Returns:
            QuerySet: The queryset containing the circle permissions for the current circle.
        """
        return CirclePermission.objects.filter(circle=self.circle_id).first()

    def list(self, request, *args, **kwargs):
        """
        List the circle permissions for the current circle.

        This method lists the circle permissions for the current circle if they exist.
        If no circle permissions are found for the current circle, a 400 Bad Request response is returned.

        Args:
            request (HttpRequest): The request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response containing the serialized data of the circle permissions for the current circle.
        """
        queryset = self.get_queryset()
        if not queryset:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(queryset)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Create a new circle permission.

        This method creates a new circle permission for the current circle if it exists.
        If no circle exists, a 400 Bad Request response is returned.
        The new circle permission data is provided in the request data.

        Args:
            request (HttpRequest): The request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response containing the serialized data of the newly created circle permission.
        """
        queryset = self.get_queryset()
        if not queryset:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        if queryset:
            serializer = self.get_serializer(queryset, data=request.data)
        else:
            serializer = self.get_serializer(queryset)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CircleSubscriberRoleViewSet(BaseCircleViewSet):
    """
    Viewset to manage circle subscriber roles.

    This viewset provides endpoints to perform CRUD (Create, Read, Update, Delete) operations on circle subscriber roles.
    Circle subscriber roles define the roles assigned to subscribers within a circle.

    Attributes:
        permission_classes: The permission classes to use for controlling access to the viewset.
        serializer_class: The serializer class to use for serializing and deserializing circle subscriber role data.
        http_method_names: The allowed HTTP methods for this viewset.

    Methods:
        get_serializer_class: Get the serializer class based on the request method.

        get_queryset: Get the queryset for retrieving circle subscriber roles.
        create: Add / update a new user to circle

    """

    permission_classes = (Authenticate,)
    serializer_class = CircleSubscriberRoleInputSerializer
    http_method_names = ("get", "post")

    def get_serializer_class(self):
        """
        Get the serializer class based on the request method.

        This method returns different serializer classes based on the request method.
        For 'GET' requests, the CircleSubscriberRoleSerializer is used to serialize circle subscriber role data.
        For other requests, the CircleSubscriberRoleInputSerializer is used for deserializing request data.

        Returns:
            Serializer: The serializer class based on the request method.
        """
        if self.request.method == "GET":
            return CircleSubscriberRoleSerializer
        else:
            return CircleSubscriberRoleInputSerializer

    def get_queryset(self):
        """
        Get the queryset for retrieving circle subscriber roles.

        This method retrieves the circle subscriber roles associated with the current circle.

        Returns:
            QuerySet: The queryset containing the circle subscriber roles for the current circle.
        """
        return CircleSubscriberRole.objects.filter(circle=self.circle_id)

    def create(self, request, *args, **kwargs):
        """
        Create/Update circle subscribers.

        This method creates circle subscribers based on the data provided in the request.
        It associates users with a specific role to the circle and performs various validation checks.

        Args:
            request (HttpRequest): The request object containing data for creating circle subscribers.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response containing the serialized data of the circle after adding subscribers.
        """
        serializer = self.serializer_class(
            data=request.data, context={"request": request, "circle_id": self.circle_id}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        circle = Circle.objects.filter(id=self.circle_id).first()
        if not circle:
            return Response({"detail": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        logged_user = request.user_id
        users = validated_data.get("users")
        user_service = User()
        for user in users:
            role = user.get("role")
            user_id = user.get("user_id")
            connected = user.get("connected")

            if user_id:
                user = user_service.details(user_id=user_id)
                if not user:
                    logger.error(f"No User exists with the given user_id: {user_id}")
                    logger.info(f"Moving on to the next user")
                else:
                    self.validate_circle_hierarchy(logged_user, user, role, circle)
                    circle_service.validate_circle_add_user(request, user, role, circle)
                    circle_service.circle_add_user(circle, user, role)
                    self.validate_transferred_circle_hierarchy(circle, user, role)
                    self.circle_add_default_admin(circle, user, role)
                    self.circle_remove_default_admin(circle, user, role)

            if connected:
                phone = phonenumbers.parse(f"+{connected}", None)
                user = user_service.get_details_from_phone(
                    country_code=phone.country_code, phone_number=phone.national_number
                )
                if not user:
                    logger.error(f"No User exists with the given phone_number: {connected}")
                    logger.info(f"Moving on to the next user")
                else:
                    self.validate_circle_hierarchy(logged_user, user, role, circle)
                    circle_service.validate_circle_add_user(request, user, role, circle)
                    circle_service.circle_add_user(circle, user, role)
                    self.validate_transferred_circle_hierarchy(circle, user, role)
                    self.circle_add_default_admin(circle, user, role)
                    self.circle_remove_default_admin(circle, user, role)

        serializer = CircleListSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def validate_circle_hierarchy(self, logged_user_id, user, role, circle):
        """
        Validate circle hierarchy.

        This method validates the circle hierarchy and updates it if necessary based on user and role.
        If the logged user is a chief admin and the role being assigned to the user is a member,
        the circle hierarchy is set to False to indicate that the circle no longer has a hierarchy.

        Args:
            logged_user_id (str): The ID of the logged-in user.
            user (dict): The details of the user being added to the circle.
            role (str): The role being assigned to the user.
            circle (Circle): The circle object.

        Returns:
            None
        """
        chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
        member = CircleRole.objects.get(role=CircleRole.MEMBER)
        logged_user_id = str(logged_user_id)
        if logged_user_id == user["id"]:
            subscriber = CircleSubscriberRole.objects.filter(
                circle=circle, user_id=logged_user_id, role=chief_admin
            ).first()
            if subscriber and role == member and circle.hierarchy:
                circle.hierarchy = False
                circle.save()

    def validate_transferred_circle_hierarchy(self, circle, user, role):
        """
        Validate and update the hierarchy status of a transferred circle based on the new Chief Admin.

        Args:
            circle (Circle): The Circle instance being transferred.
            user (dict): The user dictionary containing user information.
            role (CircleRole): The role of the user in the circle.

        Returns:
            None:
        """
        chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
        if role == chief_admin:
            circle.hierarchy = get_hierarchy_status(circle, user["id"])
            circle.save()

    def circle_add_default_admin(self, circle, user, role):
        """
        Add default admin to child circles.

        This method adds a default admin to child circles of the specified circle if the role being assigned
        to the user is a chief admin and the circle has at least one child circle.

        Args:
           circle (Circle): The circle object.
           user (dict): The details of the user being added as the default admin.
           role (str): The role being assigned to the user.

        Returns:
           None
        """
        chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
        if role == chief_admin and circle.total_children_count >= 1:
            default_admin = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
            children = get_all_children(circle=circle, include_self=False)

            for child in children:
                circle_subscriber = CircleSubscriberRole.objects.filter(
                    circle=child, user_id=user["id"]
                )
                if circle_subscriber:
                    subscriber = CircleSubscriberRole.objects.filter(
                        circle=child, user_id=user["id"], role=chief_admin
                    )
                    if not subscriber:
                        circle_subscriber.update(role=default_admin)

                else:
                    CircleSubscriberRole.objects.create(
                        circle=child, user_id=user["id"], role=default_admin
                    )
                    member_xmpp_room_subscribe(user_jid=user["jid"], room_id=child.room_id)

    def circle_remove_default_admin(self, circle, user, role):
        """
        Remove default admin from child circles.

        This method removes the default admin role from child circles of the specified circle
        if the role being assigned to the user is a member and the circle has at least one child circle.

        Args:
            circle (Circle): The circle object.
            user (dict): The details of the user whose default admin role needs to be removed.
            role (str): The role being assigned to the user.

        Returns:
            None
        """
        member = CircleRole.objects.get(role=CircleRole.MEMBER)
        if role == member and circle.total_children_count >= 1:
            default_admin = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
            children = get_all_children(circle=circle, include_self=False)

            for child in children:
                circle_subscriber = CircleSubscriberRole.objects.filter(
                    circle=child, user_id=user["id"]
                )
                if circle_subscriber:
                    subscriber = CircleSubscriberRole.objects.filter(
                        circle=child, user_id=user["id"], role=default_admin
                    )
                    if subscriber:
                        member_xmpp_room_unsubscribe(user_jid=user["jid"], room_id=child.room_id)
                        # member_unsubcribe_topic(
                        #     tokens=[user.get("fcm_token")], topic=circle.room_id
                        # )
                        subscriber.delete()


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage subscription plans.

    This viewset allows creating, listing, updating, and deleting subscription plans.

    Attributes:
       serializer_class (SubscriptionPlanSerializer): The serializer class for subscription plans.
       permission_classes (tuple): The tuple of permission classes for authentication.

    Methods:
       get_queryset: Get the queryset containing all subscription plans.
    """

    serializer_class = SubscriptionPlanSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        """
        Get the queryset containing all subscription plans.

        Returns:
            QuerySet: The queryset containing all subscription plans.
        """
        return SubscriptionPlan.objects.all()


class CustomerViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage customers.

    This viewset allows creating, listing, updating, and deleting customers.

    Attributes:
        serializer_class (CustomerSerializer): The serializer class for customers.
        permission_classes (tuple): The tuple of permission classes for authentication.

    Methods:
        get_queryset: Get the queryset containing all customers.
    """

    serializer_class = CustomerSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        """
        Get the queryset containing all customers.

        Returns:
            QuerySet: The queryset containing all customers.
        """
        return Customer.objects.all()


class AppBrandingViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage app branding.

    This viewset allows creating, listing, updating, and deleting app branding settings.

    Attributes:
        serializer_class (AppBrandingSerializer): The serializer class for app branding settings.
        permission_classes (tuple): The tuple of permission classes for authentication.

    Methods:
        get_queryset: Get the queryset containing all app branding settings.
    """

    serializer_class = AppBrandingSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        """
        Get the queryset containing all app branding settings.

        Returns:
            QuerySet: The queryset containing all app branding settings.
        """
        return AppBranding.objects.all()


class CustomFieldViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage custom fields.

    This viewset allows creating, listing, updating, and deleting custom fields.

    Attributes:
        serializer_class (CustomFieldSerializer): The serializer class for custom fields.
        permission_classes (tuple): The tuple of permission classes for authentication.

    Methods:
        get_queryset: Get the queryset containing all custom fields.
    """

    serializer_class = CustomFieldSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        """
        Get the queryset containing all custom fields.

        Returns:
            QuerySet: The queryset containing all custom fields.
        """
        return CustomField.objects.all()


class TopicViewSet(viewsets.ModelViewSet):
    """
    Viewset to manage topics.

    This viewset allows creating, listing, updating, and deleting topics.

    Attributes:
        serializer_class (TopicSerializer): The serializer class for topics.
        permission_classes (tuple): The tuple of permission classes for authentication.

    Methods:
        get_queryset: Get the queryset containing all topics.
        destroy: Delete the topic.
    """

    serializer_class = TopicSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        """
        Get the queryset containing all topics.

        Returns:
            QuerySet: The queryset containing all topics.
        """
        return Topic.objects.all()

    def destroy(self, request, *args, **kwargs):
        """
        Delete the topic.

        This method deletes the specified topic and returns a success response.

        Returns:
            Response: A response indicating the successful deletion of the topic.
        """
        try:
            topic = self.get_object()
            topic.delete()
        except Topic.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "Topic deleted successfully"}, status=status.HTTP_200_OK)


def transfer_hierarchy(circle, user):
    """
    Transfer circle hierarchy to a new user.

    This function transfers the circle hierarchy from the current chief admin to a new user.

    Args:
        circle (Circle): The circle whose hierarchy is being transferred.
        user (dict): The information of the new user who will become the chief admin.

    Returns:
        bool: True if the hierarchy transfer is successful, False otherwise.
    """
    role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
    member = CircleRole.objects.get(role=CircleRole.MEMBER)

    chief_admin = CircleSubscriberRole.objects.filter(circle=circle, role=role)
    chief_admin.update(role=member)

    circle_role = CircleSubscriberRole.objects.filter(user_id=user["id"], circle=circle)
    if not circle_role:
        CircleSubscriberRole.objects.create(user_id=user["id"], role=role, circle=circle)
        member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
    else:
        circle_role[0].role = role
        circle_role[0].save()

    # Update circle properties
    circle_properties_update(circle, hierarchy=True)
    return True


class HierarchyTransferAPIView(APIView):
    """
    API view to transfer circle hierarchy.

    This view allows transferring the hierarchy of a circle from the current chief admin to a new user.

    Attributes:
       permission_classes (tuple): The tuple of permission classes for authentication.
       serializer_class (HierarchyTransferSerializer): The serializer class for hierarchy transfer.
    """

    permission_classes = (Authenticate,)
    serializer_class = HierarchyTransferSerializer

    def post(self, request):
        """
        Transfer the circle hierarchy to a new user.

        This method handles the POST request for transferring the circle hierarchy.
        It takes the new user's information from the request data and performs the hierarchy transfer.

        Returns:
            Response: A response indicating the success or failure of the hierarchy transfer.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        circle_id = serializer.validated_data["circle_id"]
        to_user = serializer.validated_data["to_user"]
        user_service = User()
        user = user_service.details(user_id=to_user)
        if not user:
            logger.error(f"No User exists with the given user_id: {to_user}")
            return Response(
                {
                    "detail": "User matching query does not exists",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            circle = Circle.objects.get(id=circle_id)
        except Circle.DoesNotExist as exc:
            logger.error(f"{exc}")
            return Response(
                {
                    "detail": f"{exc}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if circle.parent is None:
            children = get_all_children(circle, include_self=True)
            for child in children:
                transfer_hierarchy(child, user)
        else:
            try:
                root_circle: Circle = circle.get_root()
            except circle.MultipleObjectsReturned:
                root_circle = circle.gensis_circle_id
            children = root_circle.get_family()
            for child in children:
                transfer_hierarchy(child, user)

        return Response({"message": "Hierarchy Transferred"}, status=200)


class HierarchyDeleteAPIView(APIView):
    """
    API view to delete circle hierarchy.

    This view allows deleting the hierarchy of a circle.

    Attributes:
       permission_classes (tuple): The tuple of permission classes for authentication.
       serializer_class (HierarchyDeleteSerializer): The serializer class for hierarchy deletion.
    """

    permission_classes = (Authenticate,)
    serializer_class = HierarchyDeleteSerializer

    def post(self, request):
        """
        Delete the hierarchy of a circle.

        This method handles the POST request for deleting the hierarchy of a circle.
        It takes the circle_id from the request data and performs the hierarchy deletion.

        Returns:
            Response: A response indicating the success or failure of the hierarchy deletion.
        """
        circle_id = request.data["circle_id"]
        circle = Circle.objects.filter(id=circle_id)

        if not circle:
            return Response(
                {
                    "detail": "Circle matching query does not exists",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if circle[0].parent is None:
            childrens = get_all_children(circle[0], include_self=True)
            for child in childrens:
                destroy_room(child.room_id)
                child.delete()
        else:
            family = circle.get_family()
            for child in family:
                child.delete()

        return Response({"message": "Hierarchy Deleted"}, status=200)


class CircleInviteViewSet(BulkCreateCircleInviteMixin, viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete circle invites.

    This viewset provides endpoints to manage circle invites. It supports
    bulk creation of circle invites and paginated listing of invites.

    Attributes:
        permission_classes (tuple): The tuple of permission classes for authentication.
        model (CircleInvite): The model class for circle invites.
        pagination_class (CircleInvitePagination): The pagination class for listing invites.
    """

    permission_classes = (Authenticate,)
    model = CircleInvite
    pagination_class = CircleInvitePagination

    def get_serializer_class(self):
        """
        Get the serializer class based on the action.

        Returns:
            serializer_class (class): The serializer class to use based on the action.
        """
        if self.action == "create":
            return CircleInviteCreateSerializer
        elif self.action == "update":
            return CircleInviteUpdateSerializer
        return CircleInviteSerializer

    def create(self, request, *args, **kwargs):
        """
        Create circle invites.

        This method handles the POST request for creating circle invites.

        Returns:
            Response: A response indicating the success or failure of the invite creation.
        """
        return super(CircleInviteViewSet, self).create(request, *args, **kwargs)

    def list(self, request):
        """
        List circle invites.

        This method handles the GET request for listing circle invites. It supports
        pagination and filtering based on user info.

        Returns:
            Response: A paginated response containing the list of circle invites.
        """
        params = request.GET
        user_info = logged_user_info(request)["id"]
        self._deleted_users_circle_invites(user_info)
        invites = self._get_invites(params, user_info)
        page = self.paginate_queryset(invites)
        serializer = CircleInviteResponseSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def _deleted_users_circle_invites(self, user_info):
        """
        Delete circle invites for deleted users.

        This method deletes circle invites for users who have been deleted.

        Args:
            user_info (str | None): The ID of the logged-in user.
        """
        user_details = User().details(user_id=user_info)
        if not user_details:
            invites = CircleInvite.objects.filter(Q(sender=user_info) | Q(recipient=user_info))
            invites.delete()
        invites = CircleInvite.objects.filter(sender=user_info)
        for invite in invites:
            user_service = User().details(user_id=invite.recipient)
            if not user_service:
                CircleInvite.objects.filter(
                    Q(sender=invite.recipient) | Q(recipient=invite.recipient)
                ).delete()

    def _get_invites(self, params, user_info):
        """
        Get circle invites.

        This method gets circle invites based on the given parameters.

        Args:
            params (dict): The dictionary of query parameters.
            user_info (str): The ID of the logged-in user.

        Returns:
            queryset: The queryset containing the circle invites.
        """
        invitation_type = params.get("type")
        joined = params.get("joined")
        circle = params.get("circle")
        if invitation_type == "sent":
            invites = self._get_sent_invites(user_info, circle, joined)
        elif invitation_type == "received":
            invites = self._get_received_invites(user_info, circle, joined)
        else:
            invites = CircleInvite.objects.filter(sender=user_info)
        return invites

    def _get_sent_invites(self, user_info, circle, joined):
        """
        Get circle invites sent by the specified user, filtered based on optional criteria.

        Args:
            user_info (int): ID of the sender user.
            circle (Circle or None): Optional circle filter for the invites.
            joined (str or None): Optional joined status filter (e.g., "true" or "false").

        Returns:
            QuerySet: A queryset containing the filtered circle invites.
        """
        if not circle and not joined:
            invites = CircleInvite.objects.filter(sender=user_info, joined=True)
        elif circle and joined is not None:
            joined = self._convert_to_bool(joined)
            invites = CircleInvite.objects.filter(sender=user_info, joined=joined, circle=circle)
        elif not circle and joined is not None:
            joined = self._convert_to_bool(joined)
            invites = CircleInvite.objects.filter(sender=user_info, joined=joined)
        else:
            invites = CircleInvite.objects.filter(sender=user_info)
        return invites

    def _get_received_invites(self, user_info, circle, joined):
        """
        Get circle invites received by the specified user, filtered based on optional criteria.

        Args:
            user_info (int): ID of the recipient user.
            circle (Circle or None): Optional circle filter for the invites.
            joined (str or None): Optional joined status filter (e.g., "true" or "false").

        Returns:
            QuerySet: A queryset containing the filtered circle invites.
        """
        if not circle and not joined:
            invites = CircleInvite.objects.filter(recipient=user_info, joined=False)
        elif circle and joined is not None:
            joined = self._convert_to_bool(joined)
            invites = CircleInvite.objects.filter(recipient=user_info, joined=joined, circle=circle)
        elif not circle and joined is not None:
            joined = self._convert_to_bool(joined)
            invites = CircleInvite.objects.filter(recipient=user_info, joined=joined)
        else:
            invites = CircleInvite.objects.filter(recipient=user_info, joined=False)
        return invites

    def _convert_to_bool(self, value):
        """
        Convert a string value to a boolean value.

        Args:
            value (str): The input string value.

        Returns:
            bool: The boolean representation of the input string value.
        """
        return False if value.lower() == "false" else True


def circle_invite_accept(sender, recipient, circle):
    """
    Accept a circle invitation for a user and add them as a member to the circle.

    Args:
        sender (dict): Information about the sender of the invitation.
        recipient (dict): Information about the recipient/user who is accepting the invitation.
        circle (Circle): The circle to which the invitation is being accepted.

    Returns:
        bool: True if the invitation is accepted and the user is added as a member to the circle,
              False otherwise (e.g., if the user is already a member of the circle).
    """
    circle_subscribers = CircleSubscriberRole.objects.filter(user_id=recipient["id"], circle=circle)
    member = CircleRole.objects.get(role=CircleRole.MEMBER)
    if not circle_subscribers:
        circle_service.circle_add_user(
            circle,
            recipient,
            role=member,
        )
        circle_invite = CircleInvite.objects.get(
            sender=sender["id"], recipient=recipient["id"], circle=circle
        )
        circle_invite.joined = True
        circle_invite.save()

        member_xmpp_room_subscribe(user_jid=recipient["jid"], room_id=circle.room_id)
        return True
    return False


class CircleInviteAcceptViewSet(APIView):
    """
    Viewset to accept circle invitations.

    Accepts a POST request with data to accept one or multiple circle invitations.
    The data should be in the format:
    {
        "sender": "sender_user_id",
        "recipient": "recipient_user_id",
        "circle": "circle_id"
    }

    If the recipient is not provided in the data, the authenticated user (request.user_id) will be used.
    If the request data is a list, multiple invitations can be accepted in bulk.

    Permissions:
        - The user must be authenticated.

    Serializer:
        - CircleInviteAcceptSerializer: Serializer for the invitation data.

    Response:
        - 200 OK: For successful acceptance of invitations.
        - 500 Internal Server Error: If there's an issue with the data or database.
    """

    permission_classes = (Authenticate,)
    serializer_class = CircleInviteAcceptSerializer

    def post(self, request):
        data = request.data
        user_service = User()
        user = request.user_id
        sender = data.get("sender")
        recipient = data.get("recipient") if data.get("recipient") else user
        sender = user_service.details(user_id=sender)
        recipient = user_service.details(user_id=recipient)
        circle = Circle.objects.filter(id=data.get("circle")).first()
        if not recipient or not sender or not circle:
            return Response(
                {
                    "detail": "Sorry, We are facing an issue currently. Thanks for noticing . We fix it soon"
                },
                status=500,
            )
        bulk = isinstance(request.data, list)
        if not bulk:
            circle_invite_accept(sender, recipient, circle)
            return Response({"message": "Invitation Accepted"}, status=200)

        else:
            for entry in data:
                circle_invite_accept(entry, user, circle)
        return Response({"message": "Invitations Accepted"}, status=200)


class GetCircleUniqueNameView(APIView):
    """
    API View to check the uniqueness of a circle name.

    This view allows users to check whether a given circle name is unique or already exists.
    The name to be checked should be provided as a query parameter "name" in the GET request.

    Permissions:
        - The user must be authenticated.

    Query Parameters:
        - name (str, required): The name to be checked for uniqueness.

    Response:
        - 200 OK: If the name is unique and doesn't exist in any existing circle.
        - 400 Bad Request: If the name contains special characters or emojis.
        - 400 Bad Request: If the name already exists in an existing circle.
    """

    permission_classes = (Authenticate,)
    allowed_methods = ("GET",)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="name",
                description="Check the name",
                required=True,
                type=str,
            ),
        ]
    )
    def get(self, request):
        name = request.GET.get("name")
        name = name.lower()
        if bool(re.match("^[A-Za-z0-9-]*$", name)):
            circle = Circle.objects.filter(link=name)
        else:
            return Response({"detail": "Special characters and emojis are not allowed"}, status=400)
        if circle:
            return Response({"detail": "Name already exists"}, status=400)
        else:
            return Response({"message": "Name doesn't exist"}, status=200)


class CircleLevelNameConfigViewSet(BaseCircleViewSet):
    """
    API endpoint for managing Circle Level Name Configuration.

    This viewset supports the following actions:
    - Retrieve: Get details of the Circle Level Name Configuration for a specific circle.
    - Update: Update the Circle Level Name Configuration for a specific circle.

    Permissions:
    - Requires authentication.

    HTTP Methods Allowed:
    - GET: Retrieve Circle Level Name Configuration details.
    - PUT: Update Circle Level Name Configuration.

    Example Usage:
    - GET /api/circles/hierarchy/level_name/123/ - Retrieve details for Circle Level Name Configuration.
    - PUT /api/circles/hierarchy/level_name/123/ - Update Circle Level Name Configuration.

    Note: Replace "123" with the actual circle_id in the API endpoint.
    """

    serializer_class = CircleLevelNameConfigSerializer
    permission_classes = (Authenticate,)
    http_method_names = ("get", "put")

    def get_queryset(self):
        """
        Get the queryset for Circle Level Name Configuration.

        Returns:
        - Queryset filtered by the circle_id provided in the URL.
        """
        return CircleLevelNameConfig.objects.filter(circle_id=self.kwargs.get("pk"))

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve details of the Circle Level Name Configuration for a specific circle.

        Args:
        - request: The HTTP request object.
        - *args: Additional positional arguments.
        - **kwargs: Additional keyword arguments.

        Returns:
        - Response containing Circle Level Name Configuration details.
        """
        queryset = self.get_queryset().first()
        if not queryset:
            return Response(
                {"detail": "Circle Level Name Configuration does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(queryset)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """
        Update the Circle Level Name Configuration for a specific circle.

        Args:
        - request: The HTTP request object containing update data.
        - *args: Additional positional arguments.
        - **kwargs: Additional keyword arguments.

        Error Responses:
        - 400 Bad Request: If the specified Circle Level Name Configuration does not exist.
        - 400 Bad Request: If the user does not have permission to perform the action.

        Returns:
        - Response containing the updated Circle Level Name Configuration details.
        """
        queryset = self.get_queryset().first()
        circle_id = request.data["circle"]
        if not queryset:
            return Response(
                {"detail": "Circle Level Name Configuration does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chief_admin = CircleRole.objects.filter(role=CircleRole.CHIEF_ADMIN)
        admin = CircleRole.objects.filter(role=CircleRole.ADMIN)
        circle = CircleSubscriberRole.objects.filter(
            circle=circle_id, role__in=chief_admin | admin, user_id=request.user_id
        )

        if not circle:
            return Response(
                {"detail": "You don't have permission to perform this action"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(queryset, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)


class GetAssociatedCircles(APIView):
    permission_classes = [
        Authenticate,
    ]
    allowed_methods = ("GET",)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="Filter by user_id",
                required=True,
                type=str,
            ),
        ]
    )
    def get(self, request):
        user_id = request.GET.get("user_id", "")
        circles_ids = (
            CircleSubscriberRole.objects.select_related("circle")
            .filter(user_id=user_id)
            .values_list("circle__id", flat=True)
        )

        circles = (
            Circle.objects.select_related("parent")
            .prefetch_related("topic")
            .filter(id__in=circles_ids)
        )

        serializer = CircleReportSerializer(
            circles,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)


class GetCirclesInfoByIDS(APIView):
    permission_classes = [
        Authenticate,
    ]
    allowed_methods = ("POST",)

    def post(self, request):
        serializer = CircleDetailsSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        circles = Circle.objects.select_related("parent").filter(
            id__in=serializer.data["circle_ids"]
        )

        serializer = CircleReportSerializer(
            circles,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)


class AssignUserRoomTopicView(APIView):
    """
    API view for assigning a user to a room and topic in a Circle.
    Requires API key authentication.
    """

    permission_classes = [HasAPIKey]
    allowed_methods = ("POST",)

    def post(self, request):
        """
        Assigns a user to a room and topic in a Circle.

        Parameters:
        - request (Request): The HTTP request object containing user data.

        Returns:
        - Response: HTTP response containing the result of the operation.
        """
        print("**Triggered AssignUserRoomTopicView API**")
        serializer = AssignUserRoomTopicSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        user_id = data["user_id"]
        user_jid = data["user_jid"]
        user_type = data["user_type"]
        fcm_token = data["fcm_token"]

        if not data["specialization"]:
            data["specialization"] = [None]

        if not data["program"]:
            data["program"] = [None]

        if not data["department"]:
            data["department"] = [None]
        print(f"payload : {data}")
        for specialization in data["specialization"]:
            for program in data["program"]:
                for department in data["department"]:
                    # Construct category dictionary for the current combination of values
                    category: Dict[str, Any] = {
                        "university": data["university"],
                        "program": program,
                        "stream": data["stream"],
                        "department": department,
                        "specialization": specialization,
                        "college": data["college"],
                    }
                    print(f"category payload: {category}")
                    # Query the circle
                    circle = self.get_associated_circle(category)
                    if circle:
                        # Subscribe Users(Student/Faculty) to associate circles
                        self.subscribe_user_to_circle(
                            user_id, user_jid, user_type, fcm_token, circle, data
                        )
                        return Response(
                            {
                                "message": "User assigned to associated circles and subscribed to room and FCM topic."
                            },
                            status=status.HTTP_200_OK,
                        )
                    return Response(
                        {"details: Circle records not found with the categories provided"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

    def get_associated_circle(self, category: Dict[str, Any]) -> Circle | None:
        """
        Retrieves the associated circle based on the provided category data.

        Parameters:
        - category (Dict[str, Any]): A dictionary containing category data such as university, program, stream, department, specialization, and college.

        Returns:
        - Circle | None: The associated circle if found, or None if not found.
        """
        circles = Circle.objects.filter(**category)
        print(f"Associated circles: {circles}")
        return circles.first() if circles.exists() else None

    def subscribe_user_to_room_and_topic(
        self, user_jid: str, fcm_token: str, circle: Circle
    ) -> None:
        """
        Subscribes a user to the specified ejabberd room and FCM topic associated with the given circle.

        Parameters:
        - user_jid (str): The JID (Jabber Identifier) of the user.
        - fcm_token (str): The Firebase Cloud Messaging token of the user.
        - circle (Circle): The circle to which the user will be subscribed.

        Returns:
        - None
        """
        print("**Triggered subscribe_user_to_room_and_topic method**")
        # Subscribe user to ejabberd room
        member_xmpp_room_subscribe(user_jid=user_jid, room_id=str(circle.room_id))
        logger.info(f"Subscribing User at ejabberd room for Circle: {circle}")
        print(f"Subscribing User at ejabberd room for Circle: {circle}")

        # Subscribe user to fcm topic
        member_subscribe_topic(tokens=[fcm_token], topic=str(circle.room_id))
        logger.info(f"Subscribing User at fcm topic for Circle: {circle}")
        print(f"Subscribing User at fcm topic for Circle: {circle}")

    def subscribe_user_to_circle(
        self,
        user_id: int,
        user_jid: str,
        user_type: str,
        fcm_token: str,
        circle: Circle,
        category_data: Dict[str, Any],
    ) -> None:
        """
        Subscribes a user to the specified circle based on their type and circle level.

        Parameters:
        - user_id (int): The ID of the user to subscribe.
        - user_jid (str): The JID (Jabber Identifier) of the user.
        - user_type (str): The type of user, either "Student" or "Faculty".
        - fcm_token (str): The Firebase Cloud Messaging token of the user.
        - circle (Circle): The circle to which the user will be subscribed.
        - category_data (Dict[str, Any]): A dictionary containing category data such as college, specialization, program, and department.

        Returns:
        - None
        """
        print("**Triggered subscribe_user_to_circle method**")
        if user_type == "Student" and (circle.level == 6 or circle.name == circle.specialization):
            role = CircleRole.objects.get(role=CircleRole.MEMBER)
            circle_subscriber = CircleSubscriberRole.objects.get_or_create(
                user_id=user_id, role=role, circle=circle
            )
            print(f"Circle subscriber role object: {circle_subscriber}")
            self.subscribe_user_to_room_and_topic(user_jid, fcm_token, circle)

        elif user_type == "Faculty" and circle.level in [4, 5, 6]:
            print("**Entered Faculty case")
            admin = CircleRole.objects.get(role=CircleRole.ADMIN)

            # Subscribe faculty to various circles
            subscribe_categories = {
                key: value
                for key, value in category_data.items()
                if key in ["specialization", "program", "department"]
            }

            for category_key, category_names in subscribe_categories.items():
                for name in category_names:
                    # Query the circle
                    circle_instance = Circle.objects.filter(
                        name=name,
                        university=category_data["university"],
                        stream=category_data["stream"],
                        college=category_data["college"],
                    ).first()
                    print(f"Circle instance for faculty: {circle_instance}")
                    if circle_instance:
                        # Subscribe user to the circle
                        circle_subscriber = CircleSubscriberRole.objects.get_or_create(
                            user_id=user_id, role=admin, circle=circle_instance
                        )
                        print(f"Circle subscriber role object: {circle_subscriber}")
                        # Subscribe user to the ejabberd room and fcm topic
                        self.subscribe_user_to_room_and_topic(user_jid, fcm_token, circle_instance)

                        logger.info(f"Subscribing User at associated Circle: {circle_instance}")


class AssignUserRoomTopicViewV2(APIView):
    """
    API view for assigning a user to a room and topic in a Circle.
    Requires API key authentication.
    """

    permission_classes = [HasAPIKey]
    allowed_methods = ("POST",)

    def post(self, request):
        """
        Assigns a user to a room and topic in a Circle.

        Parameters:
        - request (Request): The HTTP request object containing user data.

        Returns:
        - Response: HTTP response containing the result of the operation.
        """
        print("Triggered AssignUserRoomTopicViewV2 API")
        serializer = AssignUserRoomTopicSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        user_id = data["user_id"]
        user_jid = data["user_jid"]
        user_type = data["user_type"]
        fcm_token = data["fcm_token"]
        designation = data.get("designation", "")

        if not data["specialization"]:
            data["specialization"] = [None]

        if not data["program"]:
            data["program"] = [None]

        if not data["department"]:
            data["department"] = [None]

        for specialization in data["specialization"]:
            for program in data["program"]:
                for department in data["department"]:
                    # Construct category dictionary for the current combination of values
                    category: Dict[str, Any] = {
                        "university": data["university"] if data["university"] else None,
                        "program": program if program else None,
                        "stream": data["stream"] if data["stream"] else None,
                        "department": department if department else None,
                        "specialization": specialization if specialization else None,
                        "college": data["college"] if data["college"] else None,
                    }
                    # For category fields that are None in the data,
                    # these values will default to an empty string in the category_v2 dictionary
                    category_v2: Dict[str, Any] = {
                        "university": data["university"] if data["university"] else "",
                        "program": program if program else "",
                        "stream": data["stream"] if data["stream"] else "",
                        "department": department if department else "",
                        "specialization": specialization if specialization else "",
                        "college": data["college"] if data["college"] else "",
                    }
                    print(f"category payload: {category}")
                    print(f"category_v2 payload: {category_v2}")
                    # Query the circle
                    circle = None
                    if user_type == "Student":
                        circle: int = self.get_associated_circle(category, category_v2, user_type)

                    # Subscribe Users(Student/Faculty) to associate circles
                    self.subscribe_user_to_circle(
                        user_id,
                        user_jid,
                        user_type,
                        fcm_token,
                        circle,
                        data,
                        designation,
                    )
                    return Response(
                        {
                            "message": "User assigned to associated circles and subscribed to room and FCM topic."
                        },
                        status=status.HTTP_200_OK,
                    )

    def get_student_circle(
        self, all_circles: QuerySet[Circle], category_data: Dict[str, Any], user_type: str
    ) -> Circle:
        """
        Retrieves student circles based on the provided category data.

        Parameters:
            - all_circles (QuerySet): QuerySet of all circles.
            - category_data (dict): A dictionary containing category data such as specialization.
            - user_type (str): The type of user.

        Returns:
            - Circle | None: The student circle if found, or None if not found.
        """
        if user_type == "Student":
            circles = all_circles.filter(
                name__icontains=category_data.get("specialization"),
            )
            return self.check_circle_user_limit_create(circles)

    def check_circle_user_limit_create(self, circles: QuerySet[Circle]) -> Circle:
        """
        Checks circle user limit and creates a new circle if the limit is exceeded.

        Parameters:
            - circles (QuerySet): QuerySet of circles.

        Returns:
            - Circle: The existing or new circle.
        """
        if len(circles) > 1:
            circle = circles.last()
            if circle.circle_users_count >= 2560:
                return self.create_circle_with_incremented_version(circle)
            else:
                return circle
        else:
            circle = circles.first()
            if circle.circle_users_count >= 2560:
                return self.create_circle_with_incremented_version(circle)
            else:
                return circle

    def create_circle_with_incremented_version(self, circle: QuerySet[Circle]) -> Circle:
        """
        Creates a new circle with an incremented version number.

        Parameters:
            - circle (Circle): The existing circle.

        Returns:
            - Circle: The new circle.
        """
        # Increment version number
        current_version = circle_version_increment(circle)
        new_version = current_version + 1
        new_circle_name = f"{circle.name.strip()}-{new_version}"
        circle_data = {
            "name": new_circle_name,
            "description": circle.description,
            "privacy": circle.privacy,
            "hierarchy": circle.hierarchy,
            "gensis_circle_id": circle.gensis_circle_id,
            "level_1": circle.level_1,
            "level_2": circle.level_2,
            "level_3": circle.level_3,
            "level_4": circle.level_4,
            "level_5": circle.level_5,
            "level_6": circle.level_6,
            "level_7": circle.level_7,
            "owner_id": circle.owner_id,
            "parent": circle.parent,
            "university": circle.university,
            "college": circle.college,
            "program": circle.program,
            "department": circle.department,
            "specialization": circle.specialization,
            "designation": circle.designation,
        }
        # Create Circle
        new_circle = Circle.objects.create(**circle_data)

        # Create XMPP Room
        create_xmpp_room(new_circle)
        return new_circle

    def get_associated_circle(
        self, category: Dict[str, Any], category_v2: Dict[str, Any], user_type: str
    ) -> Circle | None:
        """
        Retrieves the associated circle based on the provided category data.

        Parameters:
            - category (Dict[str, Any]): A dictionary containing category data such as university, program, stream, department, specialization, and college.
            - user_type (str): The type of the user.

        Returns:
            - Circle | None: The associated circle if found, or None if not found.
        """
        all_circles = Circle.objects.filter(**category) | Circle.objects.filter(**category_v2)
        if all_circles:
            if len(all_circles) == 1 and all_circles.first().circle_users_count < 2560:
                return all_circles.first()
            return self.get_student_circle(all_circles, category, user_type)

        raise ValidationError({"detail": "Circle not found with the given details"})

    def subscribe_user_to_room_and_topic(
        self, user_jid: str, fcm_token: str, circle: Circle
    ) -> None:
        """
        Subscribes a user to the specified ejabberd room and FCM topic associated with the given circle.

        Parameters:
        - user_jid (str): The JID (Jabber Identifier) of the user.
        - fcm_token (str): The Firebase Cloud Messaging token of the user.
        - circle (Circle): The circle to which the user will be subscribed.

        Returns:
        - None
        """
        print("**Triggered subscribe_user_to_room_and_topic method**")
        # Subscribe user to ejabberd room
        member_xmpp_room_subscribe(user_jid=user_jid, room_id=str(circle.room_id))
        logger.info(f"Subscribing User at ejabberd room for Circle: {circle}")
        print(f"Subscribing User at ejabberd room for Circle: {circle}")

        # Subscribe user to fcm topic
        if fcm_token:
            member_subscribe_topic(tokens=[fcm_token], topic=str(circle.room_id))
            logger.info(f"Subscribing User at fcm topic for Circle: {circle}")
            print(f"Subscribing User at fcm topic for Circle: {circle}")

    def subscribe_user_to_circle_and_xmpp_room(
        self, user_id, user_jid, fcm_token, role, circle_instance
    ):
        # Subscribe user to the circle
        circle_subscriber, created = CircleSubscriberRole.objects.get_or_create(
            user_id=user_id, role=role, circle=circle_instance
        )
        logger.info(f"Subscribing User at Web server for Circle: {circle_subscriber}")

        if created:
            # Subscribe user to the ejabberd room and fcm topic
            self.subscribe_user_to_room_and_topic(user_jid, fcm_token, circle_instance)
            logger.info(f"Subscribing User at Circle room and topic: {circle_instance}")

    def subscribe_designation_circle(
        self, user_id, user_jid, fcm_token, designation: str
    ) -> Optional[Circle]:
        """
        Retrieves the circle associated with the given designation.

        Parameters:
        - designation (str): The designation of the user.

        Returns:
        - Optional[Circle]: The circle associated with the designation, or None if not found.
        """
        circles = Circle.objects.filter(
            name__icontains=designation, designation=designation, level=1
        )
        if not circles:
            raise ValidationError(
                {"detail": "Designation circle not found with provided details"},
            )
        circle_instance = self.check_circle_user_limit_create(circles)

        member = CircleRole.objects.get(role=CircleRole.MEMBER)
        # Subscribe user to the ejabberd room and fcm topic
        self.subscribe_user_to_circle_and_xmpp_room(
            user_id, user_jid, fcm_token, member, circle_instance
        )
        logger.info(f"Subscribing User at Circle room and topic: {circle_instance}")

    def subscribe_designation_based_circle_level(
        self,
        user_id: int,
        user_jid: str,
        fcm_token: str,
        category_data: Dict[str, Any],
        designation: str,
    ) -> None:
        """
        Fetches the circle based on the designation and category data.

        Parameters:
        - designation (str): The designation of the user.
        - category_data (Dict[str, Any]): A dictionary containing category data such as university, program, stream, and college.

        Returns:
        - Optional[Circle]: The fetched circle if found, otherwise None.
        """
        university_level_designations = [
            "Vice Chancellor",
            "Rector",
            "Registrar",
            "Dean C D C",
            "BOS Chairman(University)",
        ]
        college_level_designations = [
            "Principal",
            "Head of the Department (HoD)",
            "Faculty",
            "Non Teaching Staff",
            "Placement Officer",
            "BOS Chairman(College)",
        ]

        chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
        member = CircleRole.objects.get(role=CircleRole.MEMBER)

        if designation in university_level_designations:
            # Fetch circle based on university details
            circles = Circle.objects.filter(
                Q(name__icontains=category_data.get("university"))
                & Q(university=category_data.get("university"))
                & (Q(stream=None) | Q(stream=""))
                & (Q(college=None) | Q(college=""))
                & (Q(department=None) | Q(department=""))
                & (Q(program=None) | Q(program=""))
                & (Q(specialization=None) | Q(specialization=""))
            )
            circle_instance = self.check_circle_user_limit_create(circles)
            if not circles:
                raise ValidationError(
                    {"detail": "Circle not found with provided details"},
                )
            if designation not in ["Dean C D C", "BOS Chairman(University)"]:
                # Subscribe user to the circle and ejabberd room and topic
                self.subscribe_user_to_circle_and_xmpp_room(
                    user_id, user_jid, fcm_token, chief_admin, circle_instance
                )

            else:
                # Subscribe user to the circle and ejabberd room and topic
                self.subscribe_user_to_circle_and_xmpp_room(
                    user_id, user_jid, fcm_token, member, circle_instance
                )

        elif designation in college_level_designations:
            # Fetch circle based on college details
            circles = Circle.objects.filter(
                name__icontains=category_data.get("college"),
                university=category_data.get("university"),
                stream=category_data.get("stream"),
                college=category_data.get("college"),
            )
            circle_instance = self.check_circle_user_limit_create(circles)
            if not circles:
                raise ValidationError(
                    {"detail": "Circle not found with provided details"},
                )

            if designation not in ["Principal"]:
                # Subscribe user to the circle and ejabberd room and topic
                self.subscribe_user_to_circle_and_xmpp_room(
                    user_id, user_jid, fcm_token, member, circle_instance
                )
            else:
                # Subscribe user to the circle and ejabberd room and topic
                self.subscribe_user_to_circle_and_xmpp_room(
                    user_id, user_jid, fcm_token, chief_admin, circle_instance
                )

    def subscribe_user_to_circle(
        self,
        user_id: int,
        user_jid: str,
        user_type: str,
        fcm_token: str,
        circle: Circle,
        category_data: Dict[str, Any],
        designation: str,
    ) -> None:
        """
        Subscribes a user to the specified circle based on their type and circle level.

        Parameters:
        - user_id (int): The ID of the user to subscribe.
        - user_jid (str): The JID (Jabber Identifier) of the user.
        - user_type (str): The type of user, either "Student" or "Faculty".
        - fcm_token (str): The Firebase Cloud Messaging token of the user.
        - circle (Circle): The circle to which the user will be subscribed.
        - category_data (Dict[str, Any]): A dictionary containing category data such as college, specialization, program, and department.

        Returns:
        - None
        """
        print("**Triggered subscribe_user_to_circle method**")
        member = CircleRole.objects.get(role=CircleRole.MEMBER)
        if user_type == "Student" and (circle.level == 6 or circle.name == circle.specialization):
            # Subscribe user to the circle
            circle_subscriber = CircleSubscriberRole.objects.get_or_create(
                user_id=user_id, role=member, circle=circle
            )
            logger.info(f"Subscribing User at Web server for Circle: {circle_subscriber}")

            # Subscribe user to the ejabberd room and fcm topic
            self.subscribe_user_to_room_and_topic(user_jid, fcm_token, circle)
            logger.info(f"Subscribing User at Circle room and topic: {circle}")

        elif user_type == "APSCHE Head Office":
            # Apsche family circle
            circle_instance = Circle.objects.filter(name="APSCHE Family").first()
            member = CircleRole.objects.get(role=CircleRole.MEMBER)

            # Subscribe user to the ejabberd room and fcm topic
            self.subscribe_user_to_circle_and_xmpp_room(
                user_id, user_jid, fcm_token, member, circle_instance
            )
            logger.info(f"Subscribing User at Circle room and topic: {circle_instance}")

        elif user_type == "Faculty":
            print("**Entered Faculty case")

            # Subscribe to designation circle
            self.subscribe_designation_circle(user_id, user_jid, fcm_token, designation)

            # Subscribe to circle based on designation
            self.subscribe_designation_based_circle_level(
                user_id, user_jid, fcm_token, category_data, designation
            )
