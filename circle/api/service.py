from django.db.models import F, Func, Q, Value
from django.db.models.functions import Lower
from loguru import logger
from rest_framework.exceptions import ValidationError

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
    """
    Filter circles based on their names containing a given search query.

    Parameters:
        request (HttpRequest): The request object containing the search query in the GET parameters.
        circle (Circle): The root circle from which to start searching for matching circles.

    Returns:
        QuerySet: A queryset containing the circles that match the search query.

    Note:
        The search query is case-insensitive and is applied to the name field of the circles.
        The function includes the root circle and all of its children in the search.
    """
    name = request.GET.get("name").strip().lower()
    circles = get_all_children(circle, include_self=True)
    circles = Circle.objects.filter(id__in=[c.id for c in circles])
    qs = circles.annotate(name_lower=Lower("name"))
    return qs.filter(name_lower__icontains=name).order_by("-id")


def filter_circles_by_level(request, circle):
    """
    Filter circles based on their level in the hierarchy.

    Parameters:
        request (HttpRequest): The request object containing the 'level' parameter in the GET parameters.
        circle (Circle): The root circle from which to start searching for circles.

    Returns:
        QuerySet: A queryset containing the circles at the specified level in the hierarchy.

    Note:
        The function includes the root circle and all of its children in the search.
        If the specified level does not exist in the hierarchy, an empty list is returned.
    """
    level = int(request.GET.get("level", 0))
    circles = get_all_children(circle, include_self=True)
    circles_with_level = get_circle_with_level(circles)
    final_circles = circles_with_level.get(level, [])
    final_circles = Circle.objects.filter(id__in=[c.id for c in final_circles])
    return final_circles.order_by("-id")


def filter_circles_by_name_and_level(request, circle):
    """
    Filter circles based on their names containing a given search query and their level in the hierarchy.

    Parameters:
        request (HttpRequest): The request object containing the search query and level in the GET parameters.
        circle (Circle): The root circle from which to start searching for circles.

    Returns:
        QuerySet: A queryset containing the circles that match the search query and are at the specified level in the hierarchy.

    Note:
        The search query is case-insensitive and is applied to the name field of the circles.
        The function includes the root circle and all of its children in the search.
        If the specified level does not exist in the hierarchy, an empty list is returned.
    """
    name = request.GET.get("name", "").strip().lower()
    level = int(request.GET.get("level", 0))
    circles = get_all_children(circle, include_self=True)
    circles_with_level = get_circle_with_level(circles)

    final_circles = circles_with_level.get(level, [])
    final_circles = Circle.objects.filter(id__in=[c.id for c in final_circles])

    qs = final_circles.annotate(
        name_lower=Lower("name"),
        name_strip=Func(F("name_lower"), Value(" "), Value(""), function="replace"),
    )
    return qs.filter(Q(name_lower__icontains=name) | Q(name_strip__icontains=name)).order_by("-id")


def filter_circles_by_parent(request, circle):
    """
    Filter circles based on their parent circle's ID and their level in the hierarchy.

    Parameters:
        request (HttpRequest): The request object containing the 'parent' and 'level' parameters in the GET parameters.
        circle (Circle): The root circle from which to start searching for circles.

    Returns:
        QuerySet: A queryset containing the circles that have the specified parent circle ID and are at the specified level in the hierarchy.

    Note:
        The function includes the root circle and all of its children in the search.
        If the specified level does not exist in the hierarchy or the 'parent' parameter is not a valid integer, an empty list is returned.
    """
    parent = request.GET.get("parent")
    level = int(request.GET.get("level", 0))
    circles = get_all_children(circle, include_self=True)
    circles_with_level = get_circle_with_level(circles)
    final_circles = circles_with_level.get(level, [])
    final_circles = Circle.objects.filter(id__in=[c.id for c in final_circles])
    return final_circles.filter(parent=int(parent)).order_by("-id")


def get_circle_with_level(circles):
    """
    Group circles into dictionaries based on their hierarchy level.

    Parameters:
        circles (List[Circle]): A list of Circle objects representing the circles to be grouped.

    Returns:
        Dict[int, List[Circle]]: A dictionary where the keys are integers representing the hierarchy level, and the values are lists of Circle objects belonging to that level.

    Note:
        This function assumes that the input circles form a hierarchy, with each circle's parent being present in the list before the circle itself. If the input list does not follow the hierarchy structure, the function's behavior may not be as expected.
    """
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
    Add a user to a circle or update the user's role in the circle.

    Parameters:
        circle (Circle): The Circle object to which the user will be added or whose role will be updated.
        user (dict): A dictionary containing user information, including "id" and "jid" keys.
        role (CircleRole | int): The role to assign to the user in the circle. This can be either a CircleRole object or an integer representing the role.

    Note:
        - The role can be provided as either a CircleRole object or an integer representing the role. If an integer is provided, it should correspond to one of the predefined role constants defined in the CircleRole model.
        - If the role is CircleRole.MEMBER, the user will be subscribed to the XMPP room associated with the circle.
        - If the role is not CircleRole.MEMBER, the user will be assigned the specified role in the circle, and the user will also be subscribed to the XMPP room if not already subscribed.
    """
    if role.role == circle_models.CircleRole.MEMBER:
        xmpp_helpers.member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
        # xmpp_helpers.member_subscribe_topic(tokens=[user.get("fcm_token")], topic=circle.room_id)
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
        # xmpp_helpers.member_subscribe_topic(tokens=[user.get("fcm_token")], topic=circle.room_id)
    else:
        circle_models.CircleSubscriberRole.objects.filter(user_id=user["id"], circle=circle).update(
            role=role
        )


def validate_circle_add_user(request, user, role, circle):
    """
    Validate if a user can be added to a circle with the given role.

    Parameters:
        request: The HTTP request object.
        user (dict): A dictionary containing user information, including "id" and "jid" keys.
        role (CircleRole): The role to be assigned to the user in the circle.
        circle (Circle): The Circle object to which the user will be added.

    Raises:
        PermissionDenied: If the user attempting to add the new user has a role greater than the target role and the target user already has a role in the circle.

    Note:
        - The function checks if the logged-in user (request.user_id) has the required permissions to add or modify users in the circle.
        - If the target user already has a role in the circle and the logged-in user's role is higher than the target user's role, the function raises a PermissionDenied exception, indicating that a Chief Admin cannot be added/modified by a member/admin/moderator in a circle.
    """
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
            raise ValidationError(
                {
                    "detail": "Chief Admin cannot be added/modified by a member/admin/moderator in a circle"
                }
            )
