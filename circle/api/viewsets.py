import re
from typing import List, Union
import phonenumbers

from django.db.models import F, Func, Q, Value
from django.db.models.functions import Lower
from drf_spectacular.utils import OpenApiParameter, extend_schema
from loguru import logger
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from circle.api.serializers import (
    AppBrandingSerializer,
    CircleHierarchySerializer,
    CircleHierarchySearchSerializer,
    CircleRoleSerializer,
    CircleSerializer,
    CircleSubscriberRoleSerializer,
    CustomerSerializer,
    CustomFieldSerializer,
    SubscriptionPlanSerializer,
    TopicSerializer,
    CirclePermissionSerializer,
    CircleListSerializer,
    CircleUpdateSerializer,
    CircleSubscriberRoleInputSerializer,
    HierarchyTransferSerializer,
    HierarchyDeleteSerializer,
    CircleLeaveSerializer,
    CircleInviteSerializer,
    CircleInviteCreateSerializer,
    CircleInviteUpdateSerializer,
    CircleInviteResponseSerializer,
    CircleInviteAcceptSerializer,
    CircleInputSerializer,
)
from circle.api.utils import (
    get_all_children,
    get_level,
    logged_user_info,
    circle_properties_update,
    GenericPagination,
    CircleInvitePagination,
)
from circle.api.mixins import BulkCreateCircleInviteMixin
from circle.helpers.ejjaberd import (
    create_xmpp_room,
    destroy_room,
    member_xmpp_room_subscribe,
    member_xmpp_room_unsubscribe,
)
from circle.middleware.permissions import Authenticate
from circle.models import (
    AppBranding,
    Circle,
    CircleInvite,
    CirclePermission,
    CircleRole,
    CircleSubscriberRole,
    Customer,
    CustomField,
    SubscriptionPlan,
    Topic,
)
from circle.services.user import User

ERROR_MESSAGE = (
    "Sorry, We are  facing an issue currently. Thanks for noticing . We fix it soon."
)


class BaseCircleViewSet(viewsets.ModelViewSet):
    """
    This is base ViewSet for all the objects directly related to insurance claim.
    """

    @property
    def circle_id(self):
        circle_id = self.kwargs.get("circle_id")
        return circle_id

    def get_circle(self):
        return get_object_or_404(Circle.objects.all(), id=self.circle_id)

    def get_circle_by_id(self, pk):
        return get_object_or_404(Circle, id=pk)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["circle_id"] = self.kwargs.get("circle_id")
        context["request"] = self.request
        return context


class CircleViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update and delete circles.
    """

    serializer_class = CircleSerializer
    permission_classes = (Authenticate,)
    pagination_class = GenericPagination

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CircleListSerializer
        elif self.request.method in ["POST", "PUT", "PATCH"]:
            return CircleInputSerializer
        else:
            return CircleSerializer

    def get_queryset(self):
        queryset = Circle.objects.filter(owner_id=self.request.user_id)
        return queryset

    def hierarchy_limit(self, parent_id):
        parent_circle = Circle.objects.get(id=parent_id)
        parents = get_level(parent_circle)
        return parents >= 7

    def create_parent_circle_status(self, circle, user, data):
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

    def circle_add_user(self, circle, user, role: CircleRole | int):
        if role == CircleRole.MEMBER:
            member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
            CircleSubscriberRole.objects.filter(
                user_id=user["id"], circle=circle
            ).delete()

        if not role == CircleRole.MEMBER and not CircleSubscriberRole.objects.filter(
            user_id=user["id"], circle=circle
        ):
            circle_role = CircleSubscriberRole(
                circle=circle, user_id=user["id"], role=role
            )
            circle_role.save()

            # User subscribe to XMPP room
            member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
        else:
            CircleSubscriberRole.objects.filter(
                user_id=user["id"], circle=circle
            ).update(role=role)

    def circle_add_default_admins(self, circle, parent):
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
                    self.circle_add_user(
                        circle,
                        user,
                        role=role,
                    )

    def circle_add_parent_default_admins(self, parent: Circle, user):
        user_service = User()
        user = user_service.details(user_id=user["id"])

        if not user:
            logger.info(f"Moving to next admin")
            logger.error(f"No User exists with the given user_id")
        else:
            parent_circles = parent.get_parent_circles()
            for circle in parent_circles:
                parent = Circle.objects.get(id=circle.id)

                role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
                super_admins = CircleSubscriberRole.objects.filter(
                    role=role, circle=parent
                ).values_list("user_id", flat=True)

                if user["id"] not in super_admins:
                    for admin in super_admins:
                        user_service = User()
                        user = user_service.details(user_id=admin)
                        if not user:
                            logger.info(f"Moving to next admin")
                            logger.error(
                                f"No User exists with the given user_id: {admin}"
                            )
                        else:
                            role = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
                            self.circle_add_user(circle, user, role=role)

    def circle_add_topics(self, circle, topic):
        if topic:
            topics = Topic.objects.filter(id=topic[0].id)
            for topic in topics:
                circle.topic.add(topic)

    def get_circle_with_level(self, circles):
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
        Remove users from circle only if the associated users are more than one
        """
        circle_users = CircleSubscriberRole.objects.filter(circle=circle).count()
        if circle_users > 1:
            CircleSubscriberRole.objects.filter(
                user_id__in=user_ids, circle=circle
            ).delete()
            for user in user_ids:
                user_service = User()
                logger.info(f"user_id: {user}")
                user = user_service.details(user_id=user)
                if not user:
                    logger.info(f"Moving to next admin")
                    logger.error(f"No User exists with the given user_id")
                else:
                    member_xmpp_room_unsubscribe(user["jid"], circle.room_id)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="privacy",
                description="Filter by privacy of circle",
                required=False,
                type=str,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        if "privacy" in request.GET:
            privacy = request.GET.get("privacy", "")
            name = request.GET.get("name", "")
            circles = self.filter_circles_privacy(privacy, name)

        elif "name" in request.GET:
            circles = self.circle_name_search(request)

        else:
            final_circles = CircleSubscriberRole.objects.filter(user_id=request.user_id)

            circles = [circle.circle.id for circle in final_circles]
            circles = Circle.objects.filter(id__in=circles)

        queryset = circles.order_by("-id")
        page = self.paginate_queryset(queryset)

        serializer = self.get_serializer_class()(
            page, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)

    def filter_circle_privacy_name(self, queryset, name):
        # search with circle name and privacy
        if name:
            name = name.lower()
            qs = queryset.annotate(name_lower=Lower("name"))
            final_groups = qs.filter(name_lower__icontains=name)
            queryset = final_groups.order_by("name")
            return queryset
        else:
            return queryset

    def filter_circles_privacy(self, privacy, name):
        if privacy in ["public", "Public", "1", 1]:
            privacy = 1
            circles = Circle.objects.filter(privacy=privacy)
            queryset = circles.exclude(owner_id=self.request.user_id)
            results = self.filter_circle_privacy_name(queryset, name)
            return results

        if privacy in ["private", "private", "2", 2]:
            privacy = 2
            queryset = Circle.objects.filter(
                owner_id=self.request.user_id, privacy=privacy
            )
            results = self.filter_circle_privacy_name(queryset, name)
            return results

    def circle_name_search(self, request):
        # search with circle name and get list of circles
        name = request.GET["name"]
        name = name.lower()
        final_circles = CircleSubscriberRole.objects.filter(user_id=request.user_id)

        circles = [circle.circle.id for circle in final_circles]
        circles = Circle.objects.filter(id__in=circles)

        qs = circles.annotate(name_lower=Lower("name"))
        circles = qs.filter(name_lower__icontains=name)
        return circles

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        parent_circle = serializer.initial_data["parent"]
        try:
            Circle.objects.get(id=parent_circle)
        except Circle.DoesNotExist:
            return Response(
                {
                    "detail": ERROR_MESSAGE,
                    "message": "Circles matching query does not exist.",
                },
                status=500,
            )
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get("parent")
        topic = serializer.validated_data.get("topic")

        if parent:
            # Child circle limit
            limit = self.hierarchy_limit(parent.id)
            if limit:
                return Response(
                    {"data": "You reached the maximum limit of 8 child circles."},
                    status=400,
                )

            circle = serializer.save()

            # Create XMPP Room
            create_xmpp_room(circle)

            self.circle_add_topics(circle, topic)

            # Add Owner to circle and add to xmpp_room
            role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
            user_info = logged_user_info(request)
            self.circle_add_user(circle, user_info, role)

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
            self.circle_add_user(circle, user_info, role)
        serializer = CircleSerializer(circle, context={"request": request})

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        try:
            circle = Circle.objects.get(id=kwargs.get("pk"))
        except Circle.DoesNotExist:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = CircleSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        try:
            circle = Circle.objects.get(id=kwargs.get("pk"))
        except Circle.DoesNotExist:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = CircleUpdateSerializer(
            circle, context={"request": request}, data=request.data
        )
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
                    logger.error(
                        f"No User exists with the given phone_number: {connected}"
                    )
                    logger.info(f"Moving on to the next user")
                else:
                    try:
                        logger.info("Adding new user to circle")
                        role = CircleRole.objects.get(role=role)
                        self.circle_add_user(circle, user, role=role)
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
        try:
            circle = Circle.objects.get(id=pk)
            room_id = circle.room_id
        except Circle.DoesNotExist:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )
        circle.delete()
        destroy_room(room_id)
        return Response(
            {"data": "Circle Deleted Successfully"}, status=status.HTTP_200_OK
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="level",
                description="Filter by level of circle",
                required=False,
                type=int,
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
        ]
    )
    @action(
        detail=True,
        methods=["GET"],
        permission_classes=[],
    )
    def hierarchy(self, request, pk=None):
        circles = []
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )

        if "name" in request.GET and "level" not in request.GET:
            name = request.GET.get("name").strip()
            name = name.lower()

            # get all the children from hierarchy
            circles = get_all_children(circle, include_self=True)
            circles = [circle.id for circle in circles]
            circles = Circle.objects.filter(id__in=circles)

            # add a new field in queryset name_lower and search in it
            qs = circles.annotate(name_lower=Lower("name"))
            circles = qs.filter(name_lower__icontains=name)
        elif (
            "level" in request.GET
            and "name" not in request.GET
            and "parent" not in request.GET
        ):
            query = request.GET.get("level", 0)
            circles = get_all_children(circle, include_self=True)
            circles_with_level = self.get_circle_with_level(circles)
            try:
                final_circles = circles_with_level[int(query)]
                final_circles = [circle.id for circle in final_circles]
                circles = Circle.objects.filter(id__in=final_circles)
            except KeyError:
                return Response(
                    {"data": "No circle is associated with this level"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            circle = circles.order_by("-id")
            page = self.paginate_queryset(circle)
            serializer = CircleHierarchySearchSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        elif (
            "level" in request.GET
            and "name" in request.GET
            and "parent" not in request.GET
        ):
            query = request.GET.get("level", 0)
            name = request.GET.get("name").strip()
            name = name.lower()

            circles = get_all_children(circle, include_self=True)
            circles_with_level = self.get_circle_with_level(circles)
            try:
                final_circles = circles_with_level[int(query)]
                final_circles = [circle.id for circle in final_circles]
                circles = Circle.objects.filter(id__in=final_circles).annotate(
                    name_lower=Lower("name"),
                    name_strip=Func(
                        F("name_lower"),
                        Value(" "),
                        Value(""),
                        function="replace",
                    ),
                )
            except KeyError:
                return Response(
                    {"data": "No circle is associated with this level"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            circles = circles.filter(
                Q(name_lower__icontains=name) | Q(name_strip__icontains=name)
            )
        elif (
            "level" in request.GET
            and "parent" in request.GET
            and "name" not in request.GET
        ):
            query = request.GET.get("level", 0)
            parent = request.GET.get("parent")

            circles = get_all_children(circle, include_self=True)
            circles_with_level = self.get_circle_with_level(circles)
            try:
                final_circles = circles_with_level[int(query)]
                final_circles = [circle.id for circle in final_circles]
                circles = Circle.objects.filter(id__in=final_circles)
            except KeyError:
                return Response(
                    {"data": "No circle is associated with this level"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            circles = circles.filter(parent=int(parent))

        if circles:
            """Check if any query param was used (in that case we filter circle and append to list)"""
            circles = circles.order_by("-id")
            page = self.paginate_queryset(circles)
            serializer = CircleHierarchySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        else:
            """otherwise we use the circle given in the url"""
            serializer = CircleHierarchySerializer(circle)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
    )
    def info(self, request, pk=None):
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )
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
    @action(
        detail=True,
        methods=["GET"],
    )
    def users(self, request, pk=None):
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )

        role = request.GET.get("role", "")
        if role == "admins":
            role = [0, 10, 20]
            circle_users = CircleSubscriberRole.objects.filter(
                circle=circle, role__role__in=role
            )
        elif role:
            circle_users = CircleSubscriberRole.objects.filter(
                circle=circle, role__role=role
            )
        else:
            circle_users = CircleSubscriberRole.objects.filter(circle=circle)

        circle_users = circle_users.order_by("-id")
        page = self.paginate_queryset(circle_users)
        serializer = CircleSubscriberRoleSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["PUT"],
        url_path="delete/members",
        serializer_class=CircleLeaveSerializer,
    )
    def delete_members(self, request, pk=None):
        """
        Remove/unsub users from a circle

        `Payload` \n
        `user_ids`: [] # list of user_ids (QA can get it from admin panel under `CircleSubscriberRole`
        """
        try:
            circle = Circle.objects.get(id=pk)
        except Circle.DoesNotExist:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CircleLeaveSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data.get("user_ids")
        if user_ids:
            self.remove_users_from_circle(circle, user_ids)
        return Response(
            {"data": "users deleted successfully"}, status=status.HTTP_200_OK
        )

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
        """returns associated circles based on role"""
        role = request.GET.get("role", "")
        circle_ids = CircleSubscriberRole.objects.filter(
            role__role=role, user_id=request.user_id
        ).values_list("circle_id", flat=True)
        circles = Circle.objects.filter(id__in=circle_ids)
        page = self.paginate_queryset(circles)
        serializer = CircleListSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)


class CircleRoleViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update and delete circle roles.
    """

    serializer_class = CircleRoleSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        return CircleRole.objects.all()


class CirclePermissionViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update and delete circle roles.
    """

    serializer_class = CirclePermissionSerializer
    permission_classes = (Authenticate,)
    http_method_names = ("get", "post")

    def get_queryset(self):
        return CirclePermission.objects.filter(circle=self.circle_id).first()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(queryset)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):

        queryset = self.get_queryset()
        if not queryset:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )
        if queryset:
            serializer = self.get_serializer(queryset, data=request.data)
        else:
            serializer = self.get_serializer(queryset)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CircleSubscriberRoleViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update and delete circle subscriber roles.
    """

    permission_classes = (Authenticate,)
    serializer_class = CircleSubscriberRoleInputSerializer
    http_method_names = ("get", "post")

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CircleSubscriberRoleSerializer
        else:
            return CircleSubscriberRoleInputSerializer

    def get_queryset(self):
        return CircleSubscriberRole.objects.filter(circle=self.circle_id)

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request, "circle_id": self.circle_id}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        circle = Circle.objects.filter(id=self.circle_id).first()
        if not circle:
            return Response(
                {"data": "Circle does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )
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
                    self.subscribe_role_circle(circle, user, role)
                    self.circle_add_default_admin(circle, user, role)

            if connected:
                phone = phonenumbers.parse(f"+{connected}", None)
                user = user_service.get_details_from_phone(
                    country_code=phone.country_code, phone_number=phone.national_number
                )
                if not user:
                    logger.error(
                        f"No User exists with the given phone_number: {connected}"
                    )
                    logger.info(f"Moving on to the next user")
                else:
                    self.subscribe_role_circle(circle, user, role)
                    self.circle_add_default_admin(circle, user, role)

        serializer = CircleListSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def subscribe_role_circle(self, circle, user, role):
        subscriber = CircleSubscriberRole.objects.filter(
            circle=circle, user_id=user["id"]
        )
        if not subscriber:
            CircleSubscriberRole.objects.create(
                circle=circle, user_id=user["id"], role=role
            )
            # User subscribe to XMPP room
            member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
        else:
            CircleSubscriberRole.objects.filter(
                circle=circle, user_id=user["id"]
            ).update(role=role)

    def circle_add_default_admin(self, circle, user, role):
        chief_admin = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
        if role == chief_admin:
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


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete subscription plan.
    """

    serializer_class = SubscriptionPlanSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        return SubscriptionPlan.objects.all()


class CustomerViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete customer.
    """

    serializer_class = CustomerSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        return Customer.objects.all()


class AppBrandingViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete app branding.
    """

    serializer_class = AppBrandingSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        return AppBranding.objects.all()


class CustomFieldViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete CustomField.
    """

    serializer_class = CustomFieldSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        return CustomField.objects.all()


class TopicViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete circles.
    """

    serializer_class = TopicSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        return Topic.objects.all()

    def destroy(self, request, *args, **kwargs):
        try:
            topic = self.get_object()
            topic.delete()
        except Topic.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(
            {"data": "Topic deleted successfully"}, status=status.HTTP_200_OK
        )


def transfer_hierarchy(circle, user):
    role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
    member = CircleRole.objects.get(role=CircleRole.MEMBER)

    chief_admin = CircleSubscriberRole.objects.filter(circle=circle, role=role)
    chief_admin.update(role=member)

    circle_role = CircleSubscriberRole.objects.filter(user_id=user["id"], circle=circle)
    if not circle_role:
        CircleSubscriberRole.objects.create(
            user_id=user["id"], role=role, circle=circle
        )
    else:
        circle_role[0].role = role
        circle_role[0].save()

    # Update circle properties
    circle_properties_update(circle)
    return True


class HierarchyTransferAPIView(APIView):
    permission_classes = (Authenticate,)
    serializer_class = HierarchyTransferSerializer

    def post(self, request):
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
                    "detail": ERROR_MESSAGE,
                    "message": "User matching query does not exists",
                },
                status=500,
            )

        try:
            circle = Circle.objects.get(id=circle_id)
        except Circle.DoesNotExist as exc:
            logger.error(f"{exc}")
            return Response({"detail": ERROR_MESSAGE, "message": f"{exc}"}, status=500)

        if circle.parent is None:
            children = Circle.objects.filter(id=circle.id) | get_all_children(
                circle, include_self=True
            )
            for child in children:
                transfer_hierarchy(child, user)
        else:
            parents = (
                Circle.objects.filter(id=circle.parent.id)
                | circle.parent.get_parent_circles()
            )
            if parents:
                root_parent = parents
                children = parents | get_all_children(root_parent[0], include_self=True)
                for child in children:
                    transfer_hierarchy(child, user)

        return Response({"data": "Hierarchy Transferred"}, status=200)


class HierarchyDeleteAPIView(APIView):
    permission_classes = (Authenticate,)
    serializer_class = HierarchyDeleteSerializer

    def post(self, request):
        circle_id = request.data["circle_id"]
        circle = Circle.objects.filter(id=circle_id)

        if not circle:
            return Response(
                {
                    "detail": "Sorry, We are facing an issue currently. Thanks for noticing . We fix it soon."
                },
                status=500,
            )

        if circle[0].parent is None:
            childrens = circle | get_all_children(circle[0], include_self=True)
            for child in childrens:
                destroy_room(child.room_id)
                child.delete()

        else:
            parents = (
                Circle.objects.filter(pk=circle[0].parent.id)
                | circle[0].parent.get_parent_circles()
            )

            if parents:
                root_parent = parents[0]
                childrens = parents[0] | get_all_children(
                    root_parent, include_self=True
                )
                [child.delete() for child in childrens]

        return Response({"data": "Hierarchy Deleted"}, status=200)


class CircleInviteViewSet(BulkCreateCircleInviteMixin, viewsets.ModelViewSet):
    permission_classes = (Authenticate,)
    model = CircleInvite
    pagination_class = CircleInvitePagination

    def get_serializer_class(self):
        if self.action == "create":
            return CircleInviteCreateSerializer
        elif self.action == "update":
            return CircleInviteUpdateSerializer
        return CircleInviteSerializer

    def create(self, request, *args, **kwargs):
        return super(CircleInviteViewSet, self).create(request, *args, **kwargs)

    def list(self, request):
        params = request.GET
        invitation_type = params.get("type")
        joined = params.get("joined")
        circle = params.get("circle")
        user_info = logged_user_info(request)
        user_info = user_info["id"]
        if invitation_type == "sent" and not circle and not joined:
            invites = CircleInvite.objects.filter(sender=user_info, joined=True)
        elif invitation_type == "sent" and circle and joined:
            joined = False if joined == "False" or joined == "false" else True
            invites = CircleInvite.objects.filter(
                sender=user_info, joined=joined, circle=circle
            )
        elif invitation_type == "sent" and not circle and joined:
            joined = False if joined == "False" or joined == "false" else True
            invites = CircleInvite.objects.filter(sender=user_info, joined=joined)
        elif invitation_type == "received" and not circle and not joined:
            invites = CircleInvite.objects.filter(recipient=user_info, joined=False)
        elif invitation_type == "received" and circle and joined:
            joined = False if joined == "False" or joined == "false" else True
            invites = CircleInvite.objects.filter(
                recipient=user_info, joined=joined, circle=circle
            )
        elif invitation_type == "received" and not circle and joined:
            joined = False if joined == "False" or joined == "false" else True
            invites = CircleInvite.objects.filter(recipient=user_info, joined=joined)
        elif joined and circle and not invitation_type:
            joined = False if joined == "False" or joined == "false" else True
            invites = CircleInvite.objects.filter(
                sender=user_info, joined=joined, circle=circle
            )
        elif joined and circle:
            joined = False if joined == "False" or joined == "false" else True
            invites = CircleInvite.objects.filter(
                sender=user_info, joined=joined, circle=circle
            )
        elif circle and not joined:
            invites = CircleInvite.objects.filter(
                sender=user_info, joined=False, circle=circle
            )
        else:
            invites = CircleInvite.objects.filter(sender=user_info)
        page = self.paginate_queryset(invites)
        if page is not None:
            serializer = CircleInviteResponseSerializer(page, many=True)
        else:
            serializer = CircleInviteResponseSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


def circle_invite_accept(sender, recipient, circle):
    circle_subscribers = CircleSubscriberRole.objects.filter(
        user_id=recipient["id"], circle=circle
    )
    member = CircleRole.objects.get(role=CircleRole.MEMBER)
    if not circle_subscribers:
        CircleSubscriberRole.objects.create(
            user_id=recipient["id"], circle=circle, role=member
        )
        circle_invite = CircleInvite.objects.get(
            sender=sender["id"], recipient=recipient["id"], circle=circle
        )
        circle_invite.joined = True
        circle_invite.save()
        return True
    return False


class CircleInviteAcceptViewSet(APIView):
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
            return Response({"data": "Invitation Accepted"}, status=200)

        else:
            for entry in data:
                circle_invite_accept(entry, user)
        return Response({"data": "Invitations Accepted"}, status=200)


class GetCircleUniqueNameView(APIView):
    """
    API View to mute receiving messages from some other user.
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
            return Response(
                {"data": "Special characters and emojis are not allowed"}, status=400
            )
        if circle:
            return Response({"data": "Name already exists"}, status=400)
        else:
            return Response({"data": "Name doesn't exist"}, status=200)
