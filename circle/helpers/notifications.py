import re
import uuid
from typing import Dict

from pyfcm import FCMNotification

from circle.models import Circle
from circle.services.user import User
from circle_service import settings
from loguru import logger
import phonenumbers


def get_user_from_phone(phone_number: str) -> Dict:
    phone = phonenumbers.parse(f"+{phone_number}", None)

    user_service = User()
    user_details: Dict = user_service.get_details_from_phone(
        phone_number=phone.national_number, country_code=phone.country_code
    )
    return user_details


def get_message_title(from_user: Dict, circle_name: str) -> str:
    return from_user["name"] + " " + "in" + " " + '"' + circle_name + '"'


def get_ios_topic_name(topic_name: str, circle_moderation: bool) -> str:
    if circle_moderation:
        return topic_name + "-" + "moderation" + "-" + "ios"
    return topic_name + "-" + "ios"


def send_ios_notification(
    push_service,
    title: str,
    message: Dict,
    data: Dict,
    topic_name: str,
) -> None:
    # Send iOS notification
    ios_result = push_service.notify_topic_subscribers(
        topic_name=topic_name,
        message_body=message,
        message_title=title,
        content_available=True,
        delay_while_idle=False,
        badge=0,
        time_to_live=86400,
        low_priority=False,
        data_message=data,
        extra_kwargs={"mutable_content": True},
    )

    print("ios")
    print(data)
    print(ios_result)
    logger.info(f"ios result: , {ios_result}")


def send_android_notification(push_service, topic_name: str, message: Dict) -> None:
    # Send Android notification
    android_topic_name = topic_name + "-" + "android"
    print(android_topic_name)
    android_result = push_service.notify_topic_subscribers(
        topic_name=android_topic_name, data_message=message
    )
    print("android")
    print(message)
    print(android_result)
    logger.info(f"Android result: , {android_result}")
    print("Result for Circle")


def get_xml_from_media(media, xml):
    if media[0][0] == "xmlns" and media[0][1] == "'urn:xmpp:media'":
        xml = xml.replace("<body>!~~!</body>", "<body>Media</body>")
        thumbnail = xml.find("<Thumbnail>")
        if thumbnail > 0:
            start_index = thumbnail + len("<Thumbnail>")
            end_index = xml.find("</Thumbnail>")
            thumbnail_content = xml[start_index:end_index]
            xml = xml.replace(thumbnail_content, "")
            return xml
    return None


def get_xml_from_command_action(commandaction, xml):
    if commandaction[0][0] == "xmlns" and commandaction[0][1] == "'urn:xmpp:commandaction'":
        xml = xml.replace("<body>!~~!</body>", "<body>Contact</body>")
        commandmessage = xml.find("<CommandMessage>")
        if commandmessage > 0:
            start_index = commandmessage + len("<CommandMessage>")
            end_index = xml.find("</CommandMessage>")
            actual_content = xml[start_index:end_index]
            updated_content = actual_content.replace("&quot;", '"')
            xml = xml.replace(actual_content, updated_content)
            return xml
    return None


def app_notification(topic_name, message_from, message, xml):
    import os

    print("basename:    ", os.path.basename(__file__))
    print("dir_name:     ", os.path.dirname(__file__))
    print("Circle Notification")
    circle = Circle.objects.get(room_id=topic_name)
    from_user = get_user_from_phone(phone_number=message_from)

    if not from_user:
        logger.exception(f"No User exists with the given user phone details: {from_user}")
        return

    title = get_message_title(from_user, circle.name)
    data_message = {"Nick": title, "body": message, "priority": "high"}

    try:
        permission = circle.permissions.get()
    except Exception as exc:
        logger.error(f"Error occurred while getting permissions for circle: {circle.name}")
        logger.exception(exc)
        return

    ios_topic_name = get_ios_topic_name(topic_name, permission.circle_moderation)
    to = "/topics/" + ios_topic_name

    body = re.findall(r"<body>(.*?)</body>", xml)
    if body:
        name = from_user["name"]
        message_value_dict = {
            "-6": "%s has replied to a message" % name,
            "-1": "%s has forwarded a message" % name,
            "-3": "%s has liked a message" % name,
            "-4": "%s has disliked a message" % name,
            "2": "Image",
            "3": "Video",
            "4": "Audio",
            "5": "Document",
            "11": "Contact",
        }
        a = xml.find("<Bubble>") + len("<Bubble>")
        b = xml.find("</Bubble>")
        c = xml[a:b]
        no_info_messages = ["-1", "-3", "-4"]
        if body and "-" not in c:
            try:
                message = message_value_dict[c]
            except BaseException:
                pass
            media = re.findall(
                r'<MEDIA (\S+)=[""]?((?:.(?![""]?\s+(?:\S+)=|\s*\/?[>""]))+.)[""]?>',
                xml,
            )
            commandaction = re.findall(
                r'<COMMANDACTION (\S+)=[""]?((?:.(?![""]?\s+(?:\S+)=|\s*\/?[>""]))+.)[""]?>',
                xml,
            )
            if media:
                xml = get_xml_from_media(media=media, xml=xml)

            if commandaction and c == "11":
                xml = get_xml_from_command_action(commandaction=commandaction, xml=xml)

            data = {
                "delivery_receipt_requested": True,
                "score": "Circle Notification",
                "notification": {"xml": xml, "title": ios_topic_name, "body": message},
                "message_id": str(uuid.uuid4()),
                "to": to,
                "priority": "high",
                "content_available": True,
            }
            push_service = FCMNotification(api_key=settings.FCM_API_KEY)

            android_topic_name = topic_name + "-" + "android"
            send_android_notification(
                push_service=push_service,
                topic_name=android_topic_name,
                message=data_message,
            )

            send_ios_notification(
                push_service=push_service,
                title=title,
                message=message,
                data=data,
                topic_name=ios_topic_name,
            )
