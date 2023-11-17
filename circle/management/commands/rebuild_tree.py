import logging
import sys

from django.core.management.base import BaseCommand
from django.db import transaction

from circle.models import Circle

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild MPTT Tree"

    def handle(self, **options):
        try:
            with transaction.atomic():
                with Circle.objects.disable_mptt_updates():
                    Circle.objects.rebuild()
                    sys.stdout.write(self.style.SUCCESS("Tree rebuild successfully."))
        except Exception as e:
            logger.exception(e)
            sys.stdout.write(self.style.ERROR("Something went wrong while rebuilding the tree."))
