from django.db.models.signals import post_save
from django.dispatch import receiver

from circle.models import Circle, CirclePermission


@receiver(post_save, sender=Circle)
def circle_permission(sender, instance, created=False, **kwargs):
    """
    On Circle Creation, create a circle permission
    """
    if created:
        # create_link(instance)
        CirclePermission.objects.create(circle=instance)


def create_link(circle):
    if not circle.link:
        name = "".join(circle.name.split())
        # todo: add shortuuid
        unique_id = shortuuid.ShortUUID().random(length=4)
        link_name = name + "-" + unique_id
        if not Circle.objects.filter(link=link_name).exists():
            circle.link = link_name
        circle.save()
