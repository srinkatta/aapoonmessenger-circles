from django.db.models import F, Func, Q, Value
from django.db.models.functions import Lower
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

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
)
from circle.api.utils import get_all_children, get_level
from circle.helpers.ejjaberd import (
    create_xmpp_room,
    destroy_room,
    member_xmpp_room_subscribe,
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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["circle_id"] = self.kwargs.get("circle_id")
        return context


class CircleViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update and delete circles.
    """

    serializer_class = CircleSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return Circle.objects.all()

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

    def circle_add_user(self, circle, user, role):
        if not CircleSubscriberRole.objects.filter(user_id=user.id, circle=circle):
            circle_role = CircleSubscriberRole(
                circle=circle, user_id=user["id"], role=role
            )
            circle_role.save()

            # User subscribe to XMPP room
            member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)

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
                role = CircleRole.objects.get(name="Default Admin")
                # TODO: get user details from user service by using user id
                user = {}  # user details from user service
                # Adding all hidden/default admins to circle and xmpp_room
                self.circle_add_user(
                    circle,
                    user,
                    role=role,
                )

    def circle_add_parent_default_admins(self, parent: Circle, user):
        # TODO: get user details from user service
        user = {"id": 1, "name": "", "jid": ""}
        parent_circles = parent.get_parent_circles()
        for circle in parent_circles:
            parent = Circle.objects.get(id=circle.id)

            role = CircleRole.objects.get(name="Admin")
            super_admins = CircleSubscriberRole.objects.filter(
                role=role, circle=parent
            ).values_list("user_id", flat=True)

            if user["id"] not in super_admins:
                for admin in super_admins:
                    # TODO: get admin details from user service
                    admin = {"id": 1, "name": "", "jid": ""}
                    self.circle_add_user(circle, admin, role=role)

    def get_circle_with_level(self, circles):
        circles_with_level = {}
        for circle in circles:
            level = get_level(circle)
            try:
                circles_with_level[level].append(circle)
            except KeyError:
                circles_with_level[level] = [circle]
        return circles_with_level

    def create(self, request, *args, **kwargs):
        breakpoint()
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get("parent")

        if parent:
            # Child circle limit
            limit = self.hierarchy_limit(parent)
            if limit:
                return Response(
                    {"data": "You reached the maximum limit of 8 child circles."},
                    status=400,
                )
            parent = Circle.objects.get(id=parent)

            circle = serializer.save()

            # Create XMPP Room
            create_xmpp_room(circle)

            # Add Owner to circle and add to xmpp_room
            role = CircleRole.objects.get(name="Chief Admin")
            self.circle_add_user(circle, request.user, role)

            # Add default admins to circle and xmpp_room
            self.circle_add_default_admins(circle, parent)

            # Adding all admins of parent groups as default admin of this circle
            self.circle_add_parent_default_admins(parent, request.user)

        else:
            circle = serializer.save()

            # Create XMPP Room
            create_xmpp_room(circle)

            # Add Owner to circle and add to xmpp_room
            role = CircleRole.objects.get(name="Chief Admin")
            self.circle_add_user(circle, request.user, role)

        return Response(serializer.data)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            circle = self.get_object()
            room_id = circle.room_id
        except Circle.DoesNotExist:
            return Response(status=400)
        circle.delete()
        destroy_room(room_id)
        return Response({"data": "Circle Deleted Successfully"}, status=200)

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
            circles_with_level = self.get_groups_with_level(circles)
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
            circles_with_level = self.get_groups_with_level(circles)
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
            circles_with_level = self.get_groups_with_level(circles)
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
        serializer = CircleHierarchySerializer(circles)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CircleRoleViewSet(BaseCircleViewSet):
    """
    Viewset to create, list, update and delete circle roles.
    """

    serializer_class = CircleRoleSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return CircleRole.objects.all()


class CircleSubscriberRoleViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete circle subscriber roles.
    """

    serializer_class = CircleSubscriberRoleSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return CircleSubscriberRole.objects.all()


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete subscription plan.
    """

    serializer_class = SubscriptionPlanSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return SubscriptionPlan.objects.all()


class CustomerViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete customer.
    """

    serializer_class = CustomerSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return Customer.objects.all()


class AppBrandingViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete app branding.
    """

    serializer_class = AppBrandingSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return AppBranding.objects.all()


class CustomFieldViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete CustomField.
    """

    serializer_class = CustomFieldSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return CustomField.objects.all()


class TopicViewSet(viewsets.ModelViewSet):
    """
    Viewset to create, list, update and delete circles.
    """

    serializer_class = TopicSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return Topic.objects.all()
