from collections import OrderedDict
from email import charset
from typing import Set, List

from django.core.mail import send_mail
from django.template.loader import render_to_string
from loguru import logger
from rest_framework import pagination
from rest_framework.response import Response

from circle.models import Circle, CircleSubscriberRole, CircleRole
from circle.models import CircleInvite
from django.conf import settings


def get_circle_by_id(circle_id: int) -> Circle:
    """
    Retrieve a Circle object by its ID.

    Parameters:
        circle_id (int): The ID of the Circle to retrieve.

    Returns:
        Circle: The Circle object matching the given ID.

    Raises:
        Circle.DoesNotExist: If no Circle exists with the given ID.

    Note:
        - This function fetches the Circle object from the database based on its primary key (ID).
        - If the Circle with the specified ID does not exist, it raises a Circle.DoesNotExist exception.
    """
    try:
        return Circle.objects.get(pk=circle_id)
    except Circle.DoesNotExist:
        logger.error("no circle exist with the given id")


def get_level(circle: Circle):
    """
    Calculate the level of a Circle in the hierarchy.

    Parameters:
        circle (Circle): The Circle object for which the level needs to be determined.

    Returns:
        int: The level of the Circle in the hierarchy.

    Note:
        - The level of a Circle is determined by counting the number of parent Circles in the hierarchy.
        - If the Circle has no parent (i.e., it is the root of the hierarchy), the level is 0.
        - If the Circle has one parent, its level is 1, and so on.
    """
    return circle.get_level()


def get_maximum_level(circle, count):
    # TODO: revisit this
    """
    Calculate the maximum level of the hierarchy from a given Circle.

    Parameters:
        circle (Circle): The starting Circle from which to calculate the maximum level.
        count (int): The current count of levels in the hierarchy.

    Returns:
        int: The maximum level of the hierarchy starting from the given Circle.

    Note:
        - This function recursively traverses the hierarchy of Circles to find the maximum level.
        - The count parameter should be passed as 0 when initially calling the function.
    """
    childs = Circle.objects.filter(parent=circle.id)
    if childs:
        count = count + 1
        for c in childs:
            count = get_maximum_level(c, count)
    return count


def get_all_children(circle: Circle, include_self: bool = False):
    """
    Get all the children Circles of the given Circle in the hierarchy.

    Parameters:
        circle (Circle): The Circle object for which to retrieve all children.
        include_self (bool): Whether to include the given Circle in the result or not.
                             Default is False.

    Returns:
        QuerySet: A QuerySet containing all the children Circles of the given Circle.

    """
    return circle.get_descendants(include_self=include_self)


def logged_user_info(request) -> dict:
    """
    Get information about the logged-in user from the request.

    Parameters:
        request: The HTTP request object.

    Returns:
        dict: A dictionary containing information about the logged-in user.
              The dictionary includes the 'id', 'name', and 'jid' (Jabber ID) of the user.

    Note:
        - The request object is expected to have 'user_id', 'name', and 'jid' attributes
          that represent the logged-in user's information.
    """
    return {
        "id": request.user_id,
        "name": request.name,
        "jid": request.jid,
    }


def get_total_children_count(circle):
    """
    Get the total number of children Circles, including the given Circle, in the hierarchy.

    Parameters:
        circle (Circle): The Circle object for which to calculate the total children count.

    Returns:
        int: The total number of children Circles in the hierarchy, including the given Circle.

    Note:
        - This function uses the 'get_all_children' function to fetch all children Circles
          in the hierarchy, and then calculates the count.
        - The given Circle itself is also counted as a child, so the final count is reduced by 1.
    """
    total_count = get_all_children(circle, include_self=True)
    return len(total_count) - 1


def get_circle_users_count(circle):
    """
    Get the total count of distinct users associated with the given Circle.

    Parameters:
        circle (Circle): The Circle object for which to calculate the total user count.

    Returns:
        int: The total count of distinct users associated with the Circle.

    Note:
        - This function queries the 'CircleSubscriberRole' model to retrieve all user IDs
          associated with the given Circle and then counts the distinct user IDs.
        - The 'Default Admin' role users are excluded from the count.
    """
    circle_role = (
        CircleSubscriberRole.objects.filter(circle=circle)
        .values_list("user_id", flat=True)
        .distinct()
    )
    circle_users = circle_role.exclude(role__name="Default Admin")
    return circle_users.count()


def get_sub_circle_count(obj):
    """
    Get the count of sub-circles (children) under the given Circle.

    Parameters:
        obj (Circle): The Circle object for which to calculate the sub-circle count.

    Returns:
        int: The count of sub-circles (children) under the given Circle.
    """
    circles = Circle.objects.filter(parent=obj.id)
    return circles.count()


def get_gensis_circle_id(circle: Circle):
    """
    Get the ID of the genesis circle for the given Circle instance.

    Parameters:
        circle (Circle): The Circle instance for which to get the genesis circle ID.

    Returns:
        int: The ID of the genesis circle for the given Circle instance.

    Note:
        - If the given Circle is the root (has no parent), its own ID is returned.
        - If the given Circle has parents, the ID of the root parent (genesis circle) is returned.
    """
    return circle.get_root().id


def get_hierarchy_status(circle: Circle, user_id):
    """
    Get the hierarchy status of the given Circle for the specified user.

    Parameters:
        circle (Circle): The Circle object for which to check the hierarchy status.
        user_id (int): The ID of the user whose hierarchy status is to be checked.

    Returns:
        bool: True if the user has hierarchy status in the Circle, False otherwise.

    Note:
        - The hierarchy status is checked based on whether the user is the root parent or
          a member of the root parent Circle hierarchy.
    """
    if not circle.parent:
        return get_hierarchy_status_for_root(circle, user_id)

    parents = circle.get_parent_circles()
    if parents:
        root_parent = parents.order_by().first()
        return get_hierarchy_status_for_non_root(circle, root_parent, user_id)

    return False


def get_hierarchy_status_for_root(circle: Circle, user_id):
    """
    Get the hierarchy status for the specified user in the given Circle, considering the Circle as the root.

    Parameters:
        circle (Circle): The Circle object for which to check the hierarchy status.
        user_id (int): The ID of the user whose hierarchy status is to be checked.

    Returns:
        bool: True if the user has hierarchy status in the Circle, False otherwise.

    Note:
        - The function checks whether the user is the chief admin of the given Circle or any of its sub-circles.
        - If the Circle has sub-circles, it checks if the user is the chief admin of all sub-circles.
        - If the Circle has multiple owners, it checks if the user is the chief admin of any sub-circle with the same owner.
        - If the Circle is the root and has no sub-circles, it returns False.
    """
    admin = CircleSubscriberRole.objects.filter(circle=circle, user_id=user_id)
    chief_admin = admin[0].role.role if admin else ""
    childrens = get_all_children(circle, include_self=True)

    if len(childrens) > 1:
        user_role = []
        for children in childrens:
            child = CircleSubscriberRole.objects.filter(circle=children, user_id=user_id)
            tuser_role = child[0].role.role if child else ""
            result = True if tuser_role == 10 and chief_admin == 10 else False
            user_role.append(result)

        if False in user_role:
            hierarchy = [
                True if chief_admin == 10 and children.owner_id == user_id else False
                for children in childrens
            ]
            for children in childrens:
                if children.owner_id == circle.owner_id:
                    if False in hierarchy:
                        return False
                    return True
                if children.owner_id != circle.owner_id:
                    if False in hierarchy:
                        return False
                    return True
                return False
            return False

        return True

    return False


def get_hierarchy_status_for_non_root(circle, root_parent, user_id):
    """
    Get the hierarchy status for the specified user in the given Circle, considering the Circle as a non-root circle.

    Parameters:
        circle (Circle): The Circle object for which to check the hierarchy status.
        root_parent (Circle): The root parent Circle object of the given Circle.
        user_id (int): The ID of the user whose hierarchy status is to be checked.

    Returns:
        bool: True if the user has hierarchy status in the Circle, False otherwise.

    Note:
        - The function checks whether the user is the owner of the Circle or any of its sibling Circles with the same owner.
        - If the Circle has multiple owners, it checks if the user is the owner of any sibling Circle with the same owner.
    """
    childrens = get_all_children(root_parent, include_self=True)
    if len(childrens) >= 1:
        hierarchy = [
            True if children.owner_id == root_parent.owner_id else False for children in childrens
        ]
        if False in hierarchy:
            return False
        return True

    return False


def update_parent_hierarchy(parent, hierarchy: bool = False):
    """
    Update the hierarchy status and other related attributes for the parent Circle.

    Parameters:
        parent (Circle): The parent Circle object to update.
        hierarchy (bool, optional): The hierarchy status to set for the parent Circle. If not provided, the hierarchy
                                    status is determined based on the Circle's owner's hierarchy status.

    Note:
        - The function updates the hierarchy status and other attributes like sub_circle_count and total_children_count
          for the parent Circle.
        - If the 'hierarchy' parameter is not provided, the function calculates the hierarchy status based on the
          parent Circle's owner's hierarchy status.
    """
    if parent:
        parent.hierarchy = hierarchy if hierarchy else get_hierarchy_status(parent, parent.owner_id)
        parent.sub_circle_count = get_sub_circle_count(parent)
        parent.total_children_count = get_total_children_count(parent)
        parent.save()


def circle_properties_update(instance, hierarchy: bool = False):
    """
    Update the properties of the Circle instance.

    Parameters:
        instance (Circle): The Circle instance to update.
        hierarchy (bool, optional): The hierarchy status to set for the Circle. If not provided, the hierarchy status is
                                    determined based on the Circle's owner's hierarchy status.

    Note:
        - The function updates various properties of the Circle instance, including 'gensis_circle_id', 'hierarchy',
          'subcircle_count', 'total_children_count', and 'circle_users_count'.
        - If the 'hierarchy' parameter is not provided, the function calculates the hierarchy status based on the
          Circle's owner's hierarchy status.
        - Additionally, the function updates the parent Circle's hierarchy status using 'update_parent_hierarchy'.
    """
    instance.gensis_circle_id = get_gensis_circle_id(instance)
    instance.hierarchy = get_hierarchy_status(instance, instance.owner_id)
    instance.subcircle_count = get_sub_circle_count(instance)
    instance.total_children_count = get_total_children_count(instance)
    instance.circle_users_count = get_circle_users_count(instance)
    instance.save()
    update_parent_hierarchy(instance.parent, hierarchy=hierarchy)


def s3_url_extract(url):
    """
    Extract the correct S3 URL from the given URL.

    Parameters:
       url (str): The URL to extract the S3 URL from.

    Returns:
       str: The correct S3 URL based on the given URL.

    Note:
       - The function checks the provided URL for specific substrings to determine the correct S3 URL and returns it.
       - If none of the expected substrings are found, the function returns the default S3 URL: "https://media.aapoon.com".
    """
    if settings.AWS_S3_BUCKET_NAME in url or settings.AWS_CDN_DOMAIN in url:
        return f"https://{settings.AWS_CDN_DOMAIN}.{settings.HOST_DOMAIN}"
    return f"https://{settings.AWS_CDN_DOMAIN}.{settings.HOST_DOMAIN}"


def clear_bucket_from_path(path):
    """
    Clear the bucket name from the given S3 path.

    Parameters:
        path (str): The S3 path to clear the bucket name from.

    Returns:
        str: The S3 path without the bucket name.

    Note:
        - The function checks the provided path for specific substrings indicating the bucket name and removes it.
        - If the path contains either "/socialchain-dev" or "/socialchain-prod", the function removes that part from
          the path and returns the updated path.
        - If none of the expected substrings are found, the function returns the original path as-is.
    """
    if settings.AWS_S3_BUCKET_NAME in path:
        return path.replace(f"/{settings.AWS_S3_BUCKET_NAME}", "")
    return path


def abuse_mail_msg(msg):
    """
    Send an email reporting message abuse.

    Parameters:
        msg (dict): The message data containing "message_ids".

    Note:
        - The function sends an email reporting message abuse to the specified email address.
        - The email includes the content of the message identified by "message_ids" in the email body.
        - The email is sent from "support@aapoon.net" to "support@aapoon.net".
        - The email content is rendered using the template "config/email/message_abuse.html".
        - The email is sent using the "send_mail" function with "utf-8" charset.
        - Any failure during sending the email will not raise an exception due to "fail_silently=True".
    """
    subject = "Report Message Abuse"
    from_email = "support@aapoon.net"
    toemail = "support@aapoon.net"
    text = msg["message_ids"]

    context = {"content": text}

    text_content = render_to_string("config/email/message_abuse.html", context)
    charset.add_charset("utf-8", charset.SHORTEST, None, "utf-8")
    send_mail(
        subject,
        text_content,
        from_email,
        [
            toemail,
        ],
        fail_silently=True,
    )


class GenericPagination(pagination.PageNumberPagination):
    """
    Custom pagination class to modify the behavior of paginated responses.

    Attributes:
        page_size (int): Number of items to display per page. Default is 20.
        page_size_query_param (str): The query parameter name to control the page size. Default is "page_size".

    Methods:
        get_paginated_response(data): Generate the paginated response with additional data.

    Note:
        - This class extends the Django REST Framework's PageNumberPagination class to customize the pagination.
        - The page_size attribute controls the default number of items to display per page.
        - The page_size_query_param attribute specifies the query parameter name to control the page size through
          the request URL.
    """

    page_size = 20
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        """
        Customize the structure and content of the paginated response.

        Args:
            data: The paginated data.

        Returns:
            Response: A Response object containing metadata and the paginated data.
        """
        next_link = self.get_next_link() or None
        if next_link and "https" not in next_link:
            next_link = self.get_next_link().replace("http", "https")

        previous_link = self.get_previous_link() or None
        if previous_link and "https" not in previous_link:
            previous_link = self.get_previous_link().replace("http", "https")

        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", next_link),
                    ("previous", previous_link),
                    ("results", data),
                ]
            )
        )


class CircleInvitePagination(pagination.PageNumberPagination):
    """
    Custom pagination class to modify the behavior of paginated responses for circle invites.

    Attributes:
        page_size (int): Number of items to display per page. Default is 20.

    Methods:
        get_paginated_response(data): Generate the paginated response with additional data.

    Note:
        - This class extends the Django REST Framework's PageNumberPagination class to customize the pagination.
        - The page_size attribute controls the default number of items to display per page.
    """

    page_size = 20

    def get_paginated_response(self, data):
        next_link = self.get_next_link() or None
        if next_link and "https" not in next_link:
            next_link = self.get_next_link().replace("http", "https")

        previous_link = self.get_previous_link() or None
        if previous_link and "https" not in previous_link:
            previous_link = self.get_previous_link().replace("http", "https")

        params = self.request.GET
        user_info = logged_user_info(self.request)
        user_info = user_info["id"]
        joined = 0
        pending = 0
        if "type" in params:
            if params.get("type") == "sent" and params.get("circle"):
                joined = CircleInvite.objects.filter(
                    sender=user_info, joined=True, circle=params.get("circle")
                )
                pending = CircleInvite.objects.filter(
                    sender=user_info, joined=False, circle=params.get("circle")
                )
            if params.get("type") == "received" and params.get("circle"):
                joined = CircleInvite.objects.filter(
                    recipient=user_info, joined=True, circle=params.get("circle")
                )
                pending = CircleInvite.objects.filter(
                    recipient=CircleInvite, joined=False, circle=params.get("circle")
                )
            joined = joined.count() if joined else 0
            pending = pending.count() if pending else 0

            return Response(
                OrderedDict(
                    [
                        ("count", self.page.paginator.count),
                        ("next", next_link),
                        ("previous", previous_link),
                        ("joined", joined),
                        ("pending", pending),
                        ("results", data),
                    ]
                )
            )
        else:
            return Response(
                OrderedDict(
                    [
                        ("count", self.page.paginator.count),
                        ("next", next_link),
                        ("previous", previous_link),
                        ("results", data),
                    ]
                )
            )


def get_top_level_circles(user_id: int, chief_admin: CircleRole, subscribed_circle_ids) -> Set[int]:
    """
    Retrieves top level circles based on specific criteria.

    Args:
    - request: The HTTP request object.
    - chief_admin: The chief admin role.

    Returns:
    - Set of top-level circle IDs.
    """
    subscribed_circles = CircleSubscriberRole.objects.filter(
        user_id=user_id,
        role=chief_admin,
        circle__parent__isnull=False,
        circle__total_children_count__gte=1,
    ).values_list("circle_id", flat=True)

    circles = Circle.objects.filter(id__in=subscribed_circles)
    top_level_circles = set()

    for circle in circles:
        root_circle: Circle = circle.get_root()
        root_circle_role: CircleSubscriberRole = CircleSubscriberRole.objects.filter(
            user_id=user_id, circle=root_circle)
        root_circle_admin = CircleSubscriberRole.objects.filter(
            user_id=user_id, role=chief_admin, circle=root_circle
        )

        # Check ownership or admin rights before considering as a top level circle
        if not root_circle.hierarchy and root_circle.id not in subscribed_circle_ids:
            if (
                    root_circle.owner_id != str(user_id)
                    or not root_circle_admin
                    or (
                    root_circle.owner_id == str(user_id)
                    and root_circle_role != chief_admin)
            ):
                same_tree_circles = circles.filter(tree_id=circle.tree_id)
                same_tree_level = same_tree_circles.filter(level=circle.level)

                # If multiple circles are at the same level, add all to top level circles
                if len(same_tree_level) >= 2:
                    level_circles = [c.id for c in same_tree_level]
                    top_level_circles.update(level_circles)

                # If there's only one circle at this level, consider it as a top level circle
                elif len(same_tree_level) <= 1:
                    level_circles = same_tree_circles.order_by("level", "id").first()
                    top_level_circles.add(level_circles.id)
    return top_level_circles


def get_admin_circles(user_id: int, chief_admin: CircleRole) -> List[int]:
    """
    Retrieves admin created sub-circle, considering hierarchy and specific criteria.

    Args:
        user_id: The ID of the user.
        chief_admin: The chief admin role.

    Returns:
        A list of circle IDs where the user is an admin.
    """
    role_ids = []
    for role in [CircleRole.ADMIN, CircleRole.CHIEF_ADMIN]:
        role_instance = CircleRole.objects.get(role=role)
        subscribed_circles = CircleSubscriberRole.objects.filter(
            user_id=user_id,
            role=role_instance,
            circle__parent__isnull=False,
            circle__total_children_count=0,
        ).values_list("circle_id", flat=True)
        role_ids.extend(subscribed_circles)

    admin_circles = []
    for circle in Circle.objects.filter(id__in=role_ids):
        root_circle: Circle = circle.get_root()
        # Check if the user has the admin role in the root circle
        if not CircleSubscriberRole.objects.filter(
                user_id=user_id, role=chief_admin, circle=root_circle
        ).exists():
            admin_circles.append(circle.id)

    return admin_circles
