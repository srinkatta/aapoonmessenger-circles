from circle.models import Circle


def get_level(circle):
    if circle.parent is None:
        return 0
    parents = (
        Circle.objects.filter(pk=circle.parentId.pk)
        | circle.parent.get_parent_circles()
    )
    return len(parents)


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
                  on p.circle_circle = group_hierarchy.id
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
