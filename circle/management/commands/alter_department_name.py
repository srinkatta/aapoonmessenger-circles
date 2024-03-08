from django.core.management.base import BaseCommand
from loguru import logger
from circle.models import Circle


departments_upd = {
    "Arts, Humanities & Language": "M.A",
    "Commerce & Management": "M.Com/MBA",
    "Civil Engineering": "M.Tech",
    "Computer Science": "MCA",
    "Computer Science Engineering": "M.Tech",
    "Education": "M.Ed/M.Ped",
    "Electrical Engineering": "M.Tech",
    "Electronics Engineering": "M.Tech",
    "LAW": "LLM",
    "Mechanical Engineering": "M.Tech",
    "Pharmacy": "M.Pharmacy",
    "Science & Technology": "M.Sc.",
    "Science & Technology Engineering": "M.Tech",
}


class Command(BaseCommand):
    """
    Management command to update department names.
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
        try:
            pg_circles = Circle.objects.filter(program="Post Graduate")

            for circle in pg_circles:
                if circle.department in departments_upd:
                    circle.department = departments_upd[circle.department]
                    parent_circle = Circle.objects.filter(id=circle.parent.id).first()
                    if (
                        parent_circle.department in departments_upd
                        and parent_circle.name == parent_circle.department
                    ):
                        parent_circle.name = departments_upd[parent_circle.department]
                        parent_circle.department = departments_upd[parent_circle.department]
                        parent_circle.save()
                        logger.info(f"Updating Parent Department name for ID: {parent_circle.id}")
                    circle.save()
                    logger.info(f"Updating Department name for ID: {circle.id}")

        except Exception as exc:
            logger.exception("Error updating Circle properties: %s" % exc)
