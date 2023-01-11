import json
from urllib.error import HTTPError

import requests
from pyfcm import FCMNotification

from circle_service import settings


def make_request(url, method, data={}, params={}):
    try:
        headers = {
            "content-type": "application/json",
            "Authorization": settings.XMPP_AUTHORIZATION,
        }
        response = requests.request(
            method, url, data=json.dumps(data), params=params, headers=headers
        )
        response.raise_for_status()
        return response
    except (HTTPError, Exception) as e:
        print(e)
        raise


def create_xmpp_room(circle):
    url = f"{settings.XMPP_SERVER_URL}api/create_room/"
    data = {
        "name": str(circle.room_id),
        "host": settings.XMPP_HOST,
        "service": f"conference.{settings.XMPP_HOST}",
    }
    make_request(url, "POST", data=data)


def member_xmpp_room_subscribe(user_jid, room_id):
    """
    url : api/v1/subscribe_room
    user_jid : jid of the user/member which is being added to circle.
    room : room_id_circle@conference.XMPP_HOST
    nodes : urn: xmpp:mucsub: nodes:messages
    """

    url = "{}{}".format(settings.XMPP_SERVER_URL, "api/subscribe_room")
    jid = user_jid.split("@")[0]
    data = {
        "user": user_jid,
        "nick": jid,
        "room": "{}@{}.{}".format(room_id, "conference", settings.XMPP_HOST),
        "nodes": "urn:xmpp:mucsub:nodes:messages",
    }
    try:
        make_request(url, "POST", data=data)
        print("User successfully subscribed in room at XMPP server")
    except Exception as e:
        print("Error subscribing user at in room at XMPP server %s" % e)


def member_xmpp_room_unsubscribe(user_jid, room_id):
    """
    url : api/v1/unsubscribe_room
    user_jid : jid of the user/member which is being added to circle.
    room : room_id_circle@conference.XMPP_HOST
    """

    url = "{}{}".format(settings.XMPP_SERVER_URL, "api/unsubscribe_room")
    data = {
        "user": user_jid,
        "room": "{}@{}.{}".format(room_id, "conference", settings.XMPP_HOST),
    }
    try:
        make_request(url, "POST", data=data)
        print("User successfully unsubscribed in room at XMPP server")
    except Exception as e:
        print("Error unsubscribing user at in room at XMPP server %s" % e)


def member_subcribe_topic(tokens, topic):
    try:
        push_service = FCMNotification(api_key=settings.FCM_API_KEY)
        subscribed = push_service.subscribe_registration_ids_to_topic(
            tokens, str(topic)
        )
    except Exception as exc:
        print(exc)


def member_unsubcribe_topic(tokens, topic):
    try:
        push_service = FCMNotification(api_key=settings.FCM_API_KEY)
        unsubscribed = push_service.unsubscribe_registration_ids_from_topic(
            tokens, str(topic)
        )
    except Exception as exc:
        print(exc)


def destroy_room(room_id):
    """
    url : api/v1/destroy_room
    service : conference.XMPP_HOST
    name : room_id of the circle which needs to be destroyed
    """

    url = "{}{}".format(settings.XMPP_SERVER_URL, "api/destroy_room")
    data = {
        "name": str(room_id),
        "service": "{}.{}".format("conference", settings.XMPP_HOST),
    }
    try:
        make_request(url, "POST", data=data)
        print("Circle deleted successfully.")
    except Exception as e:
        print("Error destroying room at XMPP server %s" % e)
