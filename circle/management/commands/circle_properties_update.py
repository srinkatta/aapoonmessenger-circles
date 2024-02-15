from django.core.management.base import BaseCommand
from django.core.management.base import BaseCommand
from loguru import logger
from circle.models import Circle
from circle.api.utils import circle_properties_update


class Command(BaseCommand):
    """
    Management command to update Circle properties.
    """

    help = "Updates Circle properties through business logic"

    def handle(self, **options):
        """
        Handles the command execution.

        Parameters:
        - options (dict): Optional arguments passed to the command.

        Returns:
        - None
        """
        circles = Circle.objects.all()
        for circle in circles:
            try:
                circle_properties_update(circle)
                circle.save()
                logger.info("Circle properties updated successfully.")
            except Exception as exc:
                logger.exception("Error updating Circle properties: %s" % exc)
