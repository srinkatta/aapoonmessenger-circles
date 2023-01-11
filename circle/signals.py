from django.db.models.signals import post_save
from django.dispatch import receiver

from circle.models import Circle, CircleRole

# @receiver(post_save, sender=Circle)
# def circle_permission(sender, instance, created=False, **kwargs):
#     """
#     On Circle Creation, create a circle permission
#     """
#     if created:
#         CircleRole.objects.create(circle=instance)
