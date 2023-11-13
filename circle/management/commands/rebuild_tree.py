import logging
from django.db import transaction
from django.core.management.base import BaseCommand, CommandError

from circle.models import Circle, CircleSubscriberRole, CircleRole

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild MPTT Tree"

    def handle(self, **options):
        with transaction.atomic():
            with Circle.objects.disable_mptt_updates():
                Circle.objects.rebuild()
