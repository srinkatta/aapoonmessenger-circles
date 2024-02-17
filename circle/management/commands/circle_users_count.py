from django.core.management.base import BaseCommand
from loguru import logger

from circle.models import Circle
from circle.api.utils import get_circle_users_count


class Command(BaseCommand):
    """
    Command to update circle properties by setting the circle_users_count field.

    This command iterates over all Circle objects and updates each circle's properties by setting the circle_users_count field to the number of users associated with the circle.

    Attributes:
        help (str): A short description of the command's purpose.
    """

    help = "Updates circle properties by setting circle_users_count."

    def handle(self, **options):
        """
        Executes the command.

        This method is called when the management command is executed. It retrieves all Circle objects and updates each circle's properties by setting the circle_users_count field to the number of users associated with the circle.

        Parameters:
            **options: Optional arguments provided to the command.

        Returns:
            None
        """
        circles = Circle.objects.all()
        for circle in circles:
            try:
                circle.circle_users_count = get_circle_users_count(circle)
                circle.save()
                logger.info(f"Circle properties updated for circle ID: {circle.id}")
            except Exception as exc:
                logger.exception(f"Error updating Circle properties for ID {circle.id}: {exc}")
