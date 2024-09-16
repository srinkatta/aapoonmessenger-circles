import os
import re
import uuid
import phonenumbers
from typing import Dict

from pyfcm import FCMNotification

from circle.models import Circle
from circle.helpers.v2 import notifications as notification_v2
from circle_service import settings
from loguru import logger


def get_notification_message(name):
    message_value_dict = {
        "-6": "%s has replied to a message" % name,
        "-1": "%s has forwarded a message" % name,
        "-3": "%s has liked a message" % name,
        "-4": "%s has disliked a message" % name,
        "1": "Text",
        "2": "Image",
        "3": "Video",
        "4": "Audio",
        "5": "Document",
        "11": "Contact",
    }
    return message_value_dict


def process_xml_content(xml, c):
    media = re.findall(
        r'<MEDIA (\S+)=[""]?((?:.(?![""]?\s+(?:\S+)=|\s*\/?[>""]))+.)[""]?>',
        xml,
    )
    commandaction = re.findall(
        r'<COMMANDACTION (\S+)=[""]?((?:.(?![""]?\s+(?:\S+)=|\s*\/?[>""]))+.)[""]?>',
        xml,
    )
    if media:
        if media[0][0] == "xmlns" and media[0][1] == "'urn:xmpp:media'":
            xml = xml.replace("<body>!~~!</body>", "<body>Media</body>")
            thumbnail = xml.find("<Thumbnail>")
            if thumbnail > 0:
                start_index = thumbnail + len("<Thumbnail>")
                end_index = xml.find("</Thumbnail>")
                thumbnail_content = xml[start_index:end_index]
                xml = xml.replace(thumbnail_content, "")
    if commandaction and c == "11":
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


def extract_bubble_type(xml):
    """
    Extracts the bubble type from the provided XML string.
    Args:
        xml (str): The XML string containing message details.
    Returns:
        str: The bubble type extracted from the XML, or an empty string if not found.
    """
    bubble_type = re.search(r"<Bubble>(.*?)</Bubble>", xml)
    if bubble_type:
        return bubble_type.group(1)
    return ""


def extract_message_id(xml):
    """
    Extracts the message id from the provided XML string.
    Args:
        xml (str): The XML string containing message details.
    Returns:
        str: The data extracted from the XML, or an empty string if not found.
    """
    message_id_match = re.search(r"id=['\"]([^'\"]+)['\"]", xml)
    if message_id_match:
        return message_id_match.group(1)
    return ""


def extract_data(xml):
    """
    Extracts the data from the provided XML string.
    Args:
        xml (str): The XML string containing message details.
    Returns:
        str: The data extracted from the XML, or an empty string if not found.
    """
    data_match = re.findall(r"<Data>(.*?)</Data>", xml, re.DOTALL)
    if not data_match:
        pattern = r"<Data(?: xmlns='urn:xmpp:(?:Data|data)')?>(.*?)</Data>"
        data_match = re.findall(pattern, xml, re.DOTALL)
    if data_match:
        return data_match[0]
    return ""


def extract_sender_jid(xml: str) -> str:
    """
    Extracts the sender jid from the provided XML string.
    Args:
        xml (str): The XML string containing message details.
    Returns:
        str: The sender jid extracted from the XML, or an empty string if not found.
    """
    if not xml:
        return ""

    sender_jid_match = re.search(r"from='([^']+)'", xml)
    if sender_jid_match:
        from_value = sender_jid_match.group(1)
        return from_value.split("/")[0]
    return ""


def send_ios_notification(
    ios_topic_name, title, message, sender_jid, bubble_type, data, topic_name, message_id, name
):
    # Build the data payload for iOS notification
    data = {
        "delivery_receipt_requested": True,
        "score": "Circle Notification",
        "notification": {
            # "title": ios_topic_name,
            # "body": message,
            "sender_name": name,
            "sender_jid": sender_jid,
            "room_id": topic_name,
            "bubble_type": bubble_type,
            "data": data,
            "message_id": message_id,
        },
        "to": "/topics/" + ios_topic_name,
        "priority": "high",
        "content_available": True,
    }

    # Send the iOS notification
    push_service = FCMNotification(api_key=settings.FCM_API_KEY)
    ios_result = push_service.notify_topic_subscribers(
        topic_name=ios_topic_name,
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
    print(data)
    return ios_result


def send_android_notification(
    android_topic_name, title, message, sender_jid, bubble_type, data, topic_name, message_id, name
):
    data_message = {
        "Nick": title,
        "body": message,
        "priority": "high",
        "sender_jid": sender_jid,
        "room_id": topic_name,
        "bubble_type": bubble_type,
        "data": data,
        "message_id": message_id,
        "sender_name": name,
    }
    print(data_message)

    # Send the Android notification
    push_service = FCMNotification(api_key=settings.ANDROID_FCM_API_KEY)
    android_result = push_service.notify_topic_subscribers(
        topic_name=android_topic_name, data_message=data_message
    )
    return android_result


def app_notification(topic_name, message_from, message, xml):
    """
    Send a notification to mobile devices using Firebase Cloud Messaging (FCM).

    Args:
       topic_name (str): The name of the topic (circle) to send the notification.
       message_from (str): The sender of the notification (phone number).
       message (str): The message body of the notification.
       xml (str): The XML content of the notification.

    Note:
       The `make_request` function is used to send the notification request to FCM.

    Raises:
       Exception: If an error occurs during the notification process.
    """
    print("basename:    ", os.path.basename(__file__))
    print("dir_name:     ", os.path.dirname(__file__))
    print("Circle Notification")
    print(f"xml message: {xml}")
    circle = Circle.objects.get(room_id=topic_name)

    sender_name = get_sender_name_xml(xml)

    title = sender_name + " " + "in" + " " + '"' + circle.name + '"'
    try:
        permission = circle.permissions.get()
    except Exception as exc:
        logger.error(f"Error occured at getting permissions for circle: {circle.name}")
        logger.exception(exc)
        return

    if permission.circle_moderation:
        ios_topic_name = topic_name + "-" + "moderation" + "-" + "ios"
    else:
        ios_topic_name = topic_name + "-" + "ios"
    android_topic_name = topic_name + "-" + "android"

    body = re.search(r"<body>(.*?)</body>", xml)
    if body:
        name = sender_name
        message_value_dict = get_notification_message(name)
        a = xml.find("<Bubble>") + len("<Bubble>")
        b = xml.find("</Bubble>")
        c = xml[a:b]
        no_info_messages = ["-1", "-3", "-4"]
        if body and "-" not in c:
            try:
                message_value = message_value_dict[c]
                message = body.group(1) if message_value == "Text" else message_value
            except BaseException:
                pass

            # process_xml_content(xml, c)
            sender_jid = extract_sender_jid(xml)
            bubble_type = extract_bubble_type(xml)
            data = extract_data(xml)
            message_id = extract_message_id(xml)

            # Send iOS notification
            notification = notification_v2.FirebaseNotificationService()
            ios_result = notification.send_ios_notification(
                ios_topic_name,
                title,
                message,
                sender_jid,
                bubble_type,
                data,
                topic_name,
                message_id,
            )
            print("ios")
            print(ios_result)
            logger.info(f"ios result: , {ios_result}")

            # Send Android notification
            android_result = notification.send_android_notification(
                android_topic_name,
                title,
                message,
                sender_jid,
                bubble_type,
                data,
                topic_name,
                message_id,
            )
            print("android")
            print(android_result)
            logger.info(f"Android result: , {android_result}")
            print("Result for Circle")


def get_sender_name_xml(xml: str) -> str:
    """
    Extracts the sender name from the provided XML string.
    Args:
        xml (str): The XML string containing message details.
    Returns:
        str: The sender name extracted from the XML, or an empty string if not found.
    """
    if not xml:
        return ""

    sender_name_match = re.search(r"<senderName>(.*?)</senderName>", xml)
    if sender_name_match:
        return sender_name_match.group(1)
    return ""
