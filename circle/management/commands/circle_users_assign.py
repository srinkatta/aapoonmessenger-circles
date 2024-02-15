from django.core.management.base import BaseCommand
from loguru import logger

from circle.models import Circle, CircleSubscriberRole
from circle.helpers.ejjaberd import member_xmpp_room_subscribe
from circle.services.user import User


class Command(BaseCommand):
    """
    Management command to subscribe Circle users to Ejabberd rooms.

    This command iterates over all Circle objects and subscribes each user associated with the Circle to the corresponding Ejabberd room.

    Attributes:
        help (str): A short description of the command's purpose.
    """

    help = "Subscribing Circle Users to Ejabberd Room"

    def handle(self, **options):
        """
        Executes the command.

        This method is called when the management command is executed. It retrieves all Circle objects and subscribes each user associated with the Circle to the corresponding Ejabberd room.

        Parameters:
            **options: Optional arguments provided to the command.

        Returns:
            None
        """
        circles = Circle.objects.all()

        for circle in circles:
            try:
                subscribers = (
                    CircleSubscriberRole.objects.filter(circle=circle)
                    .values_list("user_id", flat=True)
                    .distinct()
                )
                for subscriber in subscribers:
                    user_service = User()
                    try:
                        user = user_service.details(user_id=subscriber)
                        member_xmpp_room_subscribe(user_jid=user["jid"], room_id=circle.room_id)
                        logger.info("Subscribing Users to ejabberd XMPP room")
                    except Exception as exc:
                        logger.exception("Error subscribing users to XMPP room: %s" % exc)

            except Exception as exc:
                logger.exception("Error subscribing users to XMPP room: %s" % exc)
