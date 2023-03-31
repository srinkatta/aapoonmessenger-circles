from django.db.models import F, Func, Q, Value
from django.db.models.functions import Lower

from circle.api.utils import (
    get_all_children,
    get_level,
)
from circle.models import (
    Circle,
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
        return qs.filter(
            Q(name_lower__icontains=name) | Q(name_strip__icontains=name)
        ).order_by("-id")
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
