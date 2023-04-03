from circle import models as circle_models
from circle.helpers import ejjaberd as xmpp_helpers


def circle_add_user(circle, user, role: circle_models.CircleRole | int):
    """
    common function to add user or update role
    """
    if role == circle_models.CircleRole.MEMBER:
        xmpp_helpers.member_xmpp_room_subscribe(
            user_jid=user["jid"], room_id=circle.room_id
        )
        circle_models.CircleSubscriberRole.objects.filter(
            user_id=user["id"], circle=circle
        ).delete()

    if (
        not role == circle_models.CircleRole.MEMBER
        and not circle_models.CircleSubscriberRole.objects.filter(
            user_id=user["id"], circle=circle
        )
    ):
        circle_role = circle_models.CircleSubscriberRole(
            circle=circle, user_id=user["id"], role=role
        )
        circle_role.save()

        # User subscribe to XMPP room
        xmpp_helpers.member_xmpp_room_subscribe(
            user_jid=user["jid"], room_id=circle.room_id
        )
    else:
        circle_models.CircleSubscriberRole.objects.filter(
            user_id=user["id"], circle=circle
        ).update(role=role)
