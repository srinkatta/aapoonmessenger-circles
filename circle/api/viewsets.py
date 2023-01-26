from typing import List

from django.db.models import F, Func, Q, Value
from django.db.models.functions import Lower
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from circle.api.serializers import (
    AppBrandingSerializer,
    CircleHierarchySerializer,
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
)
from circle.api.utils import (
    get_all_children,
    get_level,
    logged_user_info,
    circle_properties_update,
)
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
    CircleRole,
    CircleSubscriberRole,
    Customer,
    CustomField,
    SubscriptionPlan,
    Topic,
    CirclePermission,
)
from circle.services.user import User


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

    def get_serializer_class(self):
        print(self.request.method)
        if self.request.method == "GET":
            return CircleListSerializer
        else:
            return CircleSerializer

    def get_queryset(self):
        return Circle.objects.filter(owner_id=self.request.user_id)

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
        if role == 40:
            member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
        if not role == 40 and not CircleSubscriberRole.objects.filter(
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
        default_admins = CircleSubscriberRole.objects.filter(
            role__name="Default Admin", circle=parent
        ).values_list("user_id", flat=True)
        chief_admins = CircleSubscriberRole.objects.filter(
            role__name="Chief Admin", circle=parent
        ).values_list("user_id", flat=True)
        admins = default_admins | chief_admins

        for admin in admins:
            if not CircleSubscriberRole.objects.filter(user_id=admin, circle=parent):
                role = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
                # TODO: test
                user_service = User()
                user = user_service.details(user_id=admin)
                # Adding all hidden/default admins to circle and xmpp_room
                self.circle_add_user(
                    circle,
                    user,
                    role=role,
                )

    def circle_add_parent_default_admins(self, parent: Circle, user):
        user_service = User()
        user = user_service.details(user_id=user["id"])

        parent_circles = parent.get_parent_circles()
        for circle in parent_circles:
            parent = Circle.objects.get(id=circle.id)

            role = CircleRole.objects.get(role=CircleRole.ADMIN)
            super_admins = CircleSubscriberRole.objects.filter(
                role=role, circle=parent
            ).values_list("user_id", flat=True)

            if user["id"] not in super_admins:
                for admin in super_admins:
                    user_service = User()
                    user = user_service.details(user_id=admin)
                    self.circle_add_user(circle, user, role=role)

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
                user = user_service.details(user_id=user)
                member_xmpp_room_unsubscribe(user["jid"], circle.room_id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get("parent")

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

            # Add Owner to circle and add to xmpp_room
            role = CircleRole.objects.get(role=CircleRole.ADMIN)
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

            # Add Owner to circle and add to xmpp_room
            role = CircleRole.objects.get(role=CircleRole.ADMIN)
            user_info = logged_user_info(request)
            self.circle_add_user(circle, user_info, role)

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        circle = self.get_object()
        serializer = CircleSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        circle = self.get_object()
        serializer = CircleUpdateSerializer(
            circle, context={"request": request}, data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Add or Update user circle
        circle_users = serializer.validated_data.get("circle_users")
        if circle_users:
            user_service = User()
            for circle_user in circle_users:
                is_owner = circle_user.get("is_owner")
                is_admin = circle_user.get("is_admin")
                is_moderator = circle_user.get("is_moderator")
                is_default_admin = circle_user.get("is_default_admin")
                is_user = circle_user.get("is_user")
                connected = circle_user.get("connected")
                user = user_service.get_details_from_phone(phone_number=connected)

                if is_user:
                    role = 40
                    self.circle_add_user(circle, user, role=role)
                elif is_default_admin:
                    role = CircleRole.objects.get(role=CircleRole.DEFAULT_ADMIN)
                    self.circle_add_user(circle, user, role=role)
                elif is_moderator:
                    role = CircleRole.objects.get(role=CircleRole.MODERATOR)
                    self.circle_add_user(circle, user, role=role)
                elif is_admin and not is_owner:
                    role = CircleRole.objects.get(role=CircleRole.ADMIN)
                    self.circle_add_user(circle, user, role=role)
                elif is_owner:
                    role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
                    self.circle_add_user(circle, user, role=role)

        # Delete User:
        leave = serializer.validated_data.get("leave")
        user_ids = serializer.validated_data.get("user_ids")
        if leave and user_ids:
            self.remove_users_from_circle(circle, user_ids)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            circle = self.get_object()
            room_id = circle.room_id
        except Circle.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
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
        circle = self.get_object()

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
        serializer = CircleHierarchySerializer(circles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
    )
    def info(self, request, pk=None):
        circle = self.get_object()
        serializer = CircleSerializer(circle, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


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

    def get_queryset(self):
        return CirclePermission.objects.filter(circle=self.circle_id)


class CircleSubscriberRoleViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update and delete circle subscriber roles.
    """

    serializer_class = CircleSubscriberRoleSerializer
    permission_classes = (Authenticate,)

    def get_queryset(self):
        return CircleSubscriberRole.objects.filter(circle=self.circle_id)


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


def transfer_hierarchy(circle, user):
    role = CircleRole.objects.get(role=CircleRole.CHIEF_ADMIN)
    chief_admin = CircleSubscriberRole.objects.filter(circle=circle, role=role)
    chief_admin.update(
        role__name="Moderator"
    )  # Todo : For now after transfer chief admin becomes moderator

    circle_role = CircleSubscriberRole.objects.filter(user_id=user["id"], circle=circle)
    if not circle_role:
        CircleSubscriberRole.objects.create(
            user_id=user["id"],
            role__name="Chief Admin",
        )

    else:
        circle_role.role = "CHIEF ADMIN"
        circle_role.save()

    # Update circle properties
    circle_properties_update(circle)
    return True


class HierarchyTransferAPIView(APIView):
    permission_classes = (Authenticate,)

    def post(self, request):
        circle_id = request.data["circle_id"]
        to_user = request.data["to_user"]
        user = User.objects.get(id=to_user)  # TODO: Praveen Fix this
        circle = Circle.objects.filter(id=circle_id)

        if circle[0].parent is None:
            childrens = circle | get_all_children(circle[0], include_self=True)
            for children in childrens:
                transfer_hierarchy(children, user)
        else:
            parents = (
                Circle.objects.filter(id=circle[0].parent.id)
                | circle[0].parent.get_parent_circles()
            )
            if parents:
                root_parent = parents[0]
                childrens = parents[0] | get_all_children(
                    root_parent, include_self=True
                )
                for children in childrens:
                    transfer_hierarchy(children, user)

        return Response({"data": "Hierarchy Transferred"}, status=200)


class HierarchyDeleteAPIView(APIView):
    permission_classes = (Authenticate,)

    def post(self, request):
        circle_id = request.data["circle_id"]
        circle = Circle.objects.filter(id=circle_id)

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
