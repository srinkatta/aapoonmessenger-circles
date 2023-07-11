from django.db.models import F, Func, Q, Value
from django.db.models.functions import Lower
from loguru import logger
from rest_framework.exceptions import PermissionDenied

from circle import models as circle_models
from circle.api.utils import (
    get_all_children,
    get_level,
)
from circle.helpers import ejjaberd as xmpp_helpers
from circle.models import (
    Circle,
    CircleSubscriberRole,
)


def filter_circles_by_name(request, circle):
    name = request.GET.get("name").strip().lower()
    circles = get_all_children(circle, include_self=True)
    circles = Circle.objects.filter(id__in=[c.id for c in circles])
    qs = circles.annotate(name_lower=Lower("name"))
    return qs.filter(name_lower__icontains=name).order_by("-id")


def filter_circles_by_level(request, circle):
    level = int(request.GET.get("level", 0))
    circles = get_all_children(circle, include_self=True)
    circles_with_level = get_circle_with_level(circles)
    try:
        final_circles = circles_with_level[level]
        final_circles = Circle.objects.filter(id__in=[c.id for c in final_circles])
        return final_circles.order_by("-id")
    except KeyError:
        return []


def filter_circles_by_name_and_level(request, circle):
    name = request.GET.get("name").strip().lower()
    level = int(request.GET.get("level", 0))
    circles = get_all_children(circle, include_self=True)
    circles_with_level = get_circle_with_level(circles)
    try:
        final_circles = circles_with_level[level]
        final_circles = Circle.objects.filter(id__in=[c.id for c in final_circles])
        qs = final_circles.annotate(
            name_lower=Lower("name"),
            name_strip=Func(F("name_lower"), Value(" "), Value(""), function="replace"),
        )
        return qs.filter(Q(name_lower__icontains=name) | Q(name_strip__icontains=name)).order_by(
            "-id"
        )
    except KeyError:
        return []


def filter_circles_by_parent(request, circle):
    parent = request.GET.get("parent")
    level = int(request.GET.get("level", 0))
    circles = get_all_children(circle, include_self=True)
    circles_with_level = get_circle_with_level(circles)
    try:
        final_circles = circles_with_level[level]
        final_circles = Circle.objects.filter(id__in=[c.id for c in final_circles])
        return final_circles.filter(parent=int(parent)).order_by("-id")
    except (KeyError, ValueError):
        return []


def get_circle_with_level(circles):

    circles_with_level = {}
    for circle in circles:
        level = get_level(circle)
        try:
            circles_with_level[level].append(circle)
        except KeyError:
            circles_with_level[level] = [circle]
    return circles_with_level


def circle_add_user(circle, user, role: circle_models.CircleRole | int):
    """
    common function to add user or update role
    """
    if role.role == circle_models.CircleRole.MEMBER:
        xmpp_helpers.member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
        # for client verification members role save in web server
        circle_subscriber = circle_models.CircleSubscriberRole.objects.filter(
            user_id=user["id"], circle=circle
        )
        if not circle_subscriber:
            circle_models.CircleSubscriberRole.objects.create(
                user_id=user["id"], circle=circle, role=role
            )
    if (
        not role.role == circle_models.CircleRole.MEMBER
        and not circle_models.CircleSubscriberRole.objects.filter(user_id=user["id"], circle=circle)
    ):
        circle_role = circle_models.CircleSubscriberRole(
            circle=circle, user_id=user["id"], role=role
        )
        circle_role.save()

        # User subscribe to XMPP room
        xmpp_helpers.member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
    else:
        circle_models.CircleSubscriberRole.objects.filter(user_id=user["id"], circle=circle).update(
            role=role
        )


def validate_circle_add_user(request, user, role, circle):
    logged_user_instance = CircleSubscriberRole.objects.filter(
        user_id=request.user_id,
        circle=circle,
    )
    circle_user_instance = CircleSubscriberRole.objects.filter(
        user_id=user["id"],
        circle=circle,
    ).first()

    if logged_user_instance:
        logged_user_role = logged_user_instance.first().role.role

    if circle_user_instance:
        circle_user_role = circle_user_instance.role.role
        if circle_user_role < role.role and logged_user_role > circle_user_role:
            logger.error(
                "Chief Admin cannot be added/modified by a member/admin/moderator in a circle"
            )
            raise PermissionDenied(
                detail="Chief Admin cannot be added/modified by a member/admin/moderator in a circle"
            )
