from circle.models import Circle


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
        with recursive group_hierarchy (id, name, parent) as
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
    children = Circle.objects.raw(query)
    child_ids = [child.id for child in children]
    return Circle.objects.filter(id__in=child_ids)


def logged_user_info(request) -> dict:
    return {
        "id": request.user_id,
        "first_name": request.user_id,
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


def get_hierarchy_status(request, group):  # Todo : refactor the function
    if group.parent is None:
        user_info = logged_user_info(request)
        # admin = group.groupusers.filter(users_id=tenantuser.id)
        # cheif_admin = admin[0].role if admin else ""
        childrens = get_all_children(group, include_self=True)

        if len(childrens) >= 1:
            for children in childrens:
                child = children.groupusers.filter(users_id=tenantuser.id)
                tuser_role = child[0].role if child else ""
                tenantuser_role = [
                    True if tuser_role == 10 and cheif_admin == 10 else False
                ]
            if False in tenantuser_role:
                hierarchy = [
                    True
                    if cheif_admin == 10 and children.created_by == tenantuser
                    else False
                    for children in childrens
                ]
                for children in childrens:
                    if children.created_by == group.created_by:
                        if False in hierarchy:
                            return False
                        return True
                    if children.created_by != group.created_by:
                        if False in hierarchy:
                            return False
                        return True
                    return False
                return False
            return True
        return False
    parents = (
        Groups.objects.filter(pk=group.parentId.pk) | group.parentId.get_parentGroups()
    )
    if parents:
        root_parent = parents[0]
        childrens = get_all_children(root_parent, include_self=True)
        if len(childrens) >= 1:
            hierarchy = [
                True if children.created_by == root_parent.created_by else False
                for children in childrens
            ]
            if False in hierarchy:
                return False
            return True
        return False


def update_parent_hierarchy(parent_group):
    if parent:
        # parent.hierarchy = get_hierarchy_status(parent)
        parent.subcircle_count = get_sub_circle_count(parent)
        parent.total_children_count = get_total_count(parent)
        parent.save()


def circle_properties_update(request, instance):
    instance.gensis_circle_id = get_gensis_circle_id(instance)
    instance.hierarchy = get_hierarchy_status(request, instance)
    instance.subcircle_count = get_sub_circle_count(instance)
    instance.total_children_count = get_total_count(instance)
    instance.circle_users_count = get_circle_users_count(instance)
    instance.save()
    update_parent_hierarchy(instance.parent)
