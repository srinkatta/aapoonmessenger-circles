from django.core.management.base import BaseCommand
from loguru import logger

from circle.models import Circle
from circle.api.utils import get_parent_levels


class Command(BaseCommand):
    help = "Existing each Circle level information update"

    def handle(self, **options):
        circles = Circle.objects.all()
        for circle in circles:
            try:
                circle.level_1 = get_parent_levels(circle, level=1)
                circle.level_2 = get_parent_levels(circle, level=2)
                circle.level_3 = get_parent_levels(circle, level=3)
                circle.level_4 = get_parent_levels(circle, level=4)
                circle.level_5 = get_parent_levels(circle, level=5)
                circle.level_6 = get_parent_levels(circle, level=6)
                circle.level_7 = get_parent_levels(circle, level=7)
                circle.save()
                logger.info("Existing circle levels information updated successfully.")
            except Exception as exc:
                logger.exception("Error updating circle levels: %s" % exc)
