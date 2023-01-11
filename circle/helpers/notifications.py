import re
import uuid

from pyfcm import FCMNotification

from circle.models import Circle
from circle_service import settings


def app_notification(topic_name, message_from, message, xml):
    import os

    print("basename:    ", os.path.basename(__file__))
    print("dir_name:     ", os.path.dirname(__file__))
    print("Circle Notification")

    group = Circle.objects.get(room_id=topic_name)
    message_from = message_from + "@" + settings.XMPP_HOST
    # TODO: get user details from user microservie
    from_user = message_from

    title = from_user.name + " " + "in" + " " + '"' + group.name + '"'
    data_message = {"Nick": title, "body": message, "priority": "high"}
    if group.circle_moderation:
        ios_topic_name = topic_name + "-" + "moderation" + "-" + "ios"
    else:
        ios_topic_name = topic_name + "-" + "ios"
    to = "/topics/" + ios_topic_name

    body = re.findall(r"<body>(.*?)</body>", xml)
    if body:
        message_value_dict = {
            "-6": "%s has replied to a message" % from_user.name,
            "-1": "%s has forwarded a message" % from_user.name,
            "-3": "%s has liked a message" % from_user.name,
            "-4": "%s has disliked a message" % from_user.name,
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
                if media[0][0] == "xmlns" and media[0][1] == "'urn:xmpp:media'":
                    xml = xml.replace("<body>!~~!</body>", "<body>Media</body>")
                    thumbnail = xml.find("<Thumbnail>")
                    if thumbnail > 0:
                        start_index = thumbnail + len("<Thumbnail>")
                        end_index = xml.find("</Thumbnail>")
                        thumbnail_content = xml[start_index:end_index]
                        xml = xml.replace(thumbnail_content, "")
            if commandaction and c == "11":
                if (
                    commandaction[0][0] == "xmlns"
                    and commandaction[0][1] == "'urn:xmpp:commandaction'"
                ):
                    xml = xml.replace("<body>!~~!</body>", "<body>Contact</body>")
                    commandmessage = xml.find("<CommandMessage>")
                    if commandmessage > 0:
                        start_index = commandmessage + len("<CommandMessage>")
                        end_index = xml.find("</CommandMessage>")
                        actual_content = xml[start_index:end_index]
                        updated_content = actual_content.replace("&quot;", '"')
                        xml = xml.replace(actual_content, updated_content)
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

            print("ios")
            print(data)
            print(ios_result)
            android_topic_name = topic_name + "-" + "android"
            print(android_topic_name)
            android_result = push_service.notify_topic_subscribers(
                topic_name=android_topic_name, data_message=data_message
            )
            print("android")
            print(data_message)
            print(android_result)
            print("Result for Circle")


def notify_dm(
    tuser=None,
    from_user=None,
    message_from=None,
    message=None,
    xml=None,
):
    if xml:
        body = re.findall(r"<body>(.*?)</body>", xml)
        if body:
            message_value_dict = {
                "-6": "Reply",
                "-1": "Forward",
                "-3": "Like",
                "-4": "Dislike",
                "2": "Image",
                "3": "Video",
                "4": "Audio",
                "5": "Document",
                "11": "Contact",
            }
            a = xml.find("<Bubble>") + len("<Bubble>")
            b = xml.find("</Bubble>")
            c = xml[a:b]
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
                    if media[0][0] == "xmlns" and media[0][1] == "'urn:xmpp:media'":
                        xml = xml.replace("<body>!~~!</body>", "<body>Media</body>")
                        thumbnail = xml.find("<Thumbnail>")
                        if thumbnail > 0:
                            start_index = thumbnail + len("<Thumbnail>")
                            end_index = xml.find("</Thumbnail>")
                            thumbnail_content = xml[start_index:end_index]
                            xml = xml.replace(thumbnail_content, "")
                if commandaction and c == "11":
                    if (
                        commandaction[0][0] == "xmlns"
                        and commandaction[0][1] == "'urn:xmpp:commandaction'"
                    ):
                        xml = xml.replace("<body>!~~!</body>", "<body>Contact</body>")
                        commandmessage = xml.find("<CommandMessage>")
                        if commandmessage > 0:
                            start_index = commandmessage + len("<CommandMessage>")
                            end_index = xml.find("</CommandMessage>")
                            actual_content = xml[start_index:end_index]
                            updated_content = actual_content.replace("&quot;", '"')
                            xml = xml.replace(actual_content, updated_content)

                data_message = {
                    "notification": {
                        "click_action": "ReplyOrRead",
                        "xml": xml,
                        "title": from_user.name,
                        "body": message,
                        "sound": "default",
                    },
                    "to": tuser.fcm_token,
                    "Nick": from_user.name,
                    "body": message,
                    "priority": "high",
                    "content_available": True,
                }
                print(data_message)
                if tuser.fcm_token and not tuser.apns_token:
                    token = tuser.fcm_token
                    push_service = FCMNotification(api_key=settings.FCM_API_KEY)
                    print("Result for DM")
                    print("Android")
                    android_data_message = {
                        "Nick": from_user.name,
                        "body": message,
                        "priority": "high",
                    }
                    android_result = push_service.notify_single_device(
                        registration_id=token,
                        data_message=android_data_message,
                        content_available=True,
                    )
                    print(android_result)
                else:
                    token = tuser.fcm_token
                    push_service = FCMNotification(api_key=settings.FCM_API_KEY)
                    print("iPhone")
                    result = push_service.notify_single_device(
                        registration_id=token,
                        message_title=from_user.name,
                        message_body=message,
                        data_message=data_message,
                        content_available=True,
                        extra_kwargs={"mutable_content": True},
                    )
                    print(result)
                return True
