import json
from urllib.error import HTTPError

import requests
from pyfcm import FCMNotification

from circle_service import settings


def make_request(url, method, data={}, params={}):
    """
    Make an HTTP request to the specified URL with the given method, data, and parameters.

    Args:
        url (str): The URL to which the request will be sent.
        method (str): The HTTP method for the request (e.g., "GET", "POST", "PUT", "DELETE").
        data (dict, optional): The JSON data to be sent in the request body. Defaults to an empty dictionary.
        params (dict, optional): The query parameters to be included in the request. Defaults to an empty dictionary.

    Returns:
        requests.Response: The HTTP response object if the request is successful.

    Raises:
        HTTPError: If an HTTP error status code (4xx or 5xx) is returned by the server.
        Exception: If any other error occurs during the request.
    """
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
    """
    Create an XMPP room using the XMPP server's "create_room" API endpoint.

    Args:
        circle (Circle): The Circle instance containing the room ID and other relevant information.

    Raises:
        HTTPError: If an HTTP error status code (4xx or 5xx) is returned by the XMPP server.
        Exception: If any other error occurs during the request.
    """
    url = f"{settings.XMPP_SERVER_URL}api/create_room/"
    data = {
        "name": str(circle.room_id),
        "host": settings.XMPP_HOST,
        "service": f"conference.{settings.XMPP_HOST}",
    }
    make_request(url, "POST", data=data)


def member_xmpp_room_subscribe(user_jid, room_id):
    """
    Subscribe a user/member to an XMPP room.

    Args:
        user_jid (str): The JID (Jabber ID) of the user/member which is being added to the circle.
        room_id (str): The ID of the XMPP room (circle) to which the user/member is being subscribed.

    Raises:
        Exception: If an error occurs during the subscription process.
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
    Unsubscribe a user/member from an XMPP room.

    Args:
        user_jid (str): The JID (Jabber ID) of the user/member which is being removed from the circle.
        room_id (str): The ID of the XMPP room (circle) from which the user/member is being unsubscribed.

    Raises:
        Exception: If an error occurs during the unsubscription process.
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


def member_subscribe_topic(tokens, topic):
    """
    Subscribe the given registration tokens (devices) to a specific topic in Firebase Cloud Messaging (FCM).

    Args:
        tokens (list): A list of registration tokens (device tokens) that belong to the devices to be subscribed.
        topic (str): The name of the topic to which the devices will be subscribed.

    Note:
        The `FCMNotification` class is used from the `fcm-django` library to handle FCM operations.

    Raises:
        Exception: If an error occurs during the subscription process.
    """
    try:
        push_service = FCMNotification(api_key=settings.FCM_API_KEY)
        subscribed = push_service.subscribe_registration_ids_to_topic(tokens, str(topic))
    except Exception as exc:
        print(exc)


def member_unsubcribe_topic(tokens, topic):
    """
    Unsubscribe the given registration tokens (devices) from a specific topic in Firebase Cloud Messaging (FCM).

    Args:
        tokens (list): A list of registration tokens (device tokens) that belong to the devices to be unsubscribed.
        topic (str): The name of the topic from which the devices will be unsubscribed.

    Note:
        The `FCMNotification` class is used from the `fcm-django` library to handle FCM operations.

    Raises:
        Exception: If an error occurs during the unsubscription process.
    """
    try:
        push_service = FCMNotification(api_key=settings.FCM_API_KEY)
        unsubscribed = push_service.unsubscribe_registration_ids_from_topic(tokens, str(topic))
    except Exception as exc:
        print(exc)


def destroy_room(room_id):
    """
    Destroy the XMPP room with the given room_id.

    Args:
        room_id (str): The ID of the room (circle) that needs to be destroyed.

    Note:
        The `make_request` function is used to send the request to the XMPP server.

    Raises:
        Exception: If an error occurs during the room destruction process.
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
