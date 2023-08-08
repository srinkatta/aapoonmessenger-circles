from django.db.models.signals import post_save
from django.dispatch import receiver

from circle.api.utils import circle_properties_update
from circle.models import Circle, CirclePermission
import shortuuid


@receiver(post_save, sender=Circle)
def circle_permission(sender, instance, created=False, **kwargs):
    """
    Signal to create circle permission when a Circle instance is created.

    Args:
        sender: The model class.
        instance: The Circle instance being saved.
        created: A boolean value indicating if the Circle is just created.
        **kwargs: Additional keyword arguments.

    Returns:
        None
    """
    if created:
        create_link(instance)
        CirclePermission.objects.create(circle=instance)


def create_link(circle):
    """
    Function to generate and set a unique link for a Circle instance.

    Args:
        circle: The Circle instance for which to generate and set the unique link.

    Returns:
        None
    """
    if not circle.link:
        name = "".join(circle.name.split())
        unique_id = shortuuid.ShortUUID().random(length=4)
        link_name = name + "-" + unique_id
        if not Circle.objects.filter(link=link_name).exists():
            circle.link = link_name
        circle.save()


@receiver(post_save, sender=Circle)
def circle_properties(sender, instance, created=False, **kwargs):
    """
    Signal to calculate and save properties of a Circle instance when it is created.

    Args:
        sender: The model class.
        instance: The Circle instance being saved.
        created: A boolean value indicating if the Circle is just created.
        **kwargs: Additional keyword arguments.

    Returns:
        None
    """
    if created:
        circle_properties_update(instance)
