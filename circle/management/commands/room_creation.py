import uuid
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from circle.models import Circle
from loguru import logger


class Command(BaseCommand):
    """
    Command to update circle properties by assigning unique room IDs.

    This command iterates over all Circle objects and assigns a unique room ID to each circle that does not already have one.
    The room ID is generated using the UUID version 4 algorithm.

    Attributes:
        help (str): A short description of the command's purpose.
    """

    help = "Updates circle properties by assigning unique room IDs."

    def handle(self, **options):
        """
        Executes the command.

        This method is called when the management command is executed. It retrieves all Circle objects and assigns a unique room ID to each circle that does not already have one.

        Parameters:
            **options: Optional arguments provided to the command.

        Returns:
            None
        """
        circles = Circle.objects.all()
        for circle in circles:
            try:
                if not circle.room_id:
                    circle.room_id = str(uuid.uuid4())
                    circle.updated_at = timezone.now()
                    circle.save()
                    logger.info(f"Circle properties updated for circle ID: {circle.id}")
            except ObjectDoesNotExist as exc:
                logger.error(f"Circle with ID {circle.id} not found: {exc}")
            except Exception as exc:
                logger.exception(f"Error updating Circle properties for ID {circle.id}: {exc}")
