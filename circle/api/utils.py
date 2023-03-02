from email import charset

from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string

from circle.models import Circle, CircleSubscriberRole
from rest_framework import pagination
from collections import OrderedDict
from rest_framework.response import Response
from circle.models import CircleInvite


def get_level(circle):
    if circle.parent is None:
        return 0
    parents = (
        Circle.objects.filter(pk=circle.parent.pk) | circle.parent.get_parent_circles()
    )
    return len(parents)


def get_maximum_level(circle, count):
    childs = Circle.objects.filter(parent=circle.id)
    if childs:
        count = count + 1
        for c in childs:
            count = get_maximum_level(c, count)
    return count


def get_all_children(circle, include_self=True):
    query = f"""
        with recursive group_hierarchy (id, name, parent_id) as
        (
          select     id,
                     name,
                     parent_id
          from       circle_circle
          where      parent_id = {circle.pk}
          union all
          select     p.id,
                     p.name,
                     p.parent_id
          from       circle_circle p
          inner join group_hierarchy
                  on p.parent_id = group_hierarchy.id
        )
        select * from group_hierarchy;
        """
    return Circle.objects.filter(get_children_filters(circle, include_self))


def get_children_filters(circle, include_self=True):
    filters = Q()
    if include_self:
        filters |= Q(pk=circle.pk)
    for c in Circle.objects.filter(parent=circle):
        _r = get_children_filters(c, include_self=True)
        if _r:
            filters |= _r
    return filters


def logged_user_info(request) -> dict:
    return {
        "id": request.user_id,
        "first_name": request.last_name,
        "last_name": request.last_name,
        "jid": request.jid,
    }


def get_total_count(circle):
    total_count = get_all_children(circle, include_self=False)
    return len(total_count)


def get_circle_users_count(circle):
    circle_role = (
        CircleSubscriberRole.objects.filter(circle=circle)
        .values_list("user_id", flat=True)
        .distinct()
    )
    circle_users = circle_role.exclude(role__name="Default Admin")
    return circle_users.count()


def get_sub_circle_count(obj):
    circles = Circle.objects.filter(parent=obj.id)
    return circles.count()


def get_gensis_circle_id(instance):
    if instance.parent is None:
        return instance.id
    parents = (
        Circle.objects.filter(pk=instance.parent.pk)
        | instance.parent.get_parent_circles()
    )
    if parents:
        root_parent = parents[0]
        return root_parent.id
    else:
        return instance.id


def get_hierarchy_status(circle, user_id):
    if not circle.parent:
        admin = CircleSubscriberRole.objects.filter(circle=circle, user_id=user_id)

        chief_admin = admin[0].role.role if admin else ""
        childrens = get_all_children(circle, include_self=True)

        if len(childrens) >= 1:
            user_role = []
            for children in childrens:
                child = CircleSubscriberRole.objects.filter(
                    circle=children, user_id=user_id
                )
                tuser_role = child[0].role.role if child else ""
                user_role = [True if tuser_role == 10 and chief_admin == 10 else False]
            if False in user_role:
                hierarchy = [
                    True
                    if chief_admin == 10 and children.owner_id == user_id
                    else False
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
    parents = (
        Circle.objects.filter(pk=circle.parent.pk) | circle.parent.get_parent_circles()
    )
    if parents:
        root_parent = parents[0]
        childrens = get_all_children(root_parent, include_self=True)
        if len(childrens) >= 1:
            hierarchy = [
                True if children.owner_id == root_parent.owner_id else False
                for children in childrens
            ]
            if False in hierarchy:
                return False
            return True
        return False


def update_parent_hierarchy(parent):
    if parent:
        parent.hierarchy = get_hierarchy_status(parent, parent.owner_id)
        parent.sub_circle_count = get_sub_circle_count(parent)
        parent.total_children_count = get_total_count(parent)
        parent.save()


def circle_properties_update(instance):
    instance.gensis_circle_id = get_gensis_circle_id(instance)
    instance.hierarchy = get_hierarchy_status(instance, instance.owner_id)
    instance.subcircle_count = get_sub_circle_count(instance)
    instance.total_children_count = get_total_count(instance)
    instance.circle_users_count = get_circle_users_count(instance)
    instance.save()
    update_parent_hierarchy(instance.parent)


def s3_url_extract(url):
    if "socialchain-dev" in url or "mediadev" in url:
        return "https://mediadev.aapoon.com"
    elif "socialchain-prod" in url or "media.aapoon.com" in url:
        return "https://media.aapoon.com"
    else:
        return "https://media.aapoon.com"


def clear_bucket_from_path(path):
    if "socialchain-dev" in path:
        path = path.replace("/socialchain-dev", "")
        return path
    elif "socialchain-prod" in path:
        path = path.replace("/socialchain-prod", "")
        return path
    else:
        return path


def abuse_mail_msg(msg):
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
    page_size = 20
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    (
                        "next",
                        self.get_next_link().replace("http", "https")
                        if self.get_next_link()
                        else None,
                    ),
                    (
                        "previous",
                        self.get_previous_link().replace("http", "https")
                        if self.get_previous_link()
                        else None,
                    ),
                    ("results", data),
                ]
            )
        )


class CircleInvitePagination(pagination.PageNumberPagination):
    page_size = 20

    def get_paginated_response(self, data):
        params = self.request.GET
        user_info = logged_user_info(self.request)
        user_info = user_info["id"]
        joined = 0
        pending = 0
        if "type" in params:
            import pdb

            pdb.set_trace()
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
                        (
                            "next",
                            self.get_next_link().replace("http", "https")
                            if self.get_next_link()
                            else None,
                        ),
                        (
                            "previous",
                            self.get_previous_link().replace("http", "https")
                            if self.get_previous_link()
                            else None,
                        ),
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
                        (
                            "next",
                            self.get_next_link().replace("http", "https")
                            if self.get_next_link()
                            else None,
                        ),
                        (
                            "previous",
                            self.get_previous_link().replace("http", "https")
                            if self.get_previous_link()
                            else None,
                        ),
                        ("results", data),
                    ]
                )
            )
