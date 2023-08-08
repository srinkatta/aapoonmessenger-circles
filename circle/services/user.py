import uuid
from typing import (
    Any,
    Dict,
)

import requests
from requests import Response

from circle_service import settings
from loguru import logger
import uuid
from typing import (
    Any,
    Dict,
)

import requests
from loguru import logger
from requests import Response

from circle_service import settings


class User:
    """
    Utility class to interact with the user microservice and retrieve user details.

    Attributes:
        base_url (str): Base URL of the user microservice.
        user_detail_service_url (str): URL to retrieve user details based on user ID or user JID.
        user_detail_phone_service_url (str): URL to retrieve user details based on phone number.
        headers (dict): Request headers including an authorization token.

    Methods:
        details(user_id, user_jid): Retrieve user details based on user ID or user JID.
        get_details_from_phone(phone_number, country_code): Retrieve user details based on phone number.

    Note:
        - This class is designed to interact with the user microservice API.
        - The methods 'details' and 'get_details_from_phone' use the 'requests' library to make HTTP requests.
    """

    def __init__(self):
        self.base_url = settings.USER_MICROSERVICE_URL
        self.user_detail_service_url = f"{self.base_url}api/users/user_details/"
        self.user_detail_phone_service_url = f"{self.base_url}api/users/user_details_phone/"
        self.headers = {"Authorization": settings.USER_MICROSERVICE_API_KEY}

    def details(self, user_id: int = None, user_jid=None) -> Dict:  # type: ignore
        """
        Retrieve user details based on either the user ID or the user JID (Jabber ID).

        Args:
            user_id (int, optional): The user ID of the user. Defaults to None.
            user_jid (str, optional): The Jabber ID (JID) of the user. Defaults to None.

        Returns:
            dict: A dictionary containing the user details.

        Note:
            - If both user_id and user_jid are provided, the user details will be fetched based on user_id.
            - If neither user_id nor user_jid is provided, the user details will not be fetched, and an empty dictionary will be returned.
        """
        request_data: dict = self._prepare_request(user_id, user_jid)
        try:
            response: Response = requests.post(
                self.user_detail_service_url,
                json=request_data,
                headers=self.headers,
            )
            response.raise_for_status()
            user_detail = self._prepare_response_body(response)
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as exc:
            logger.exception(f"Error getting user details: {exc}")
            user_detail = {}
        return user_detail

    def get_details_from_phone(self, phone_number: str = "", country_code: str = "") -> Dict:
        """
        Retrieve user details based on the phone number and country code.

        Args:
            phone_number (str, optional): The phone number of the user. Defaults to an empty string.
            country_code (str, optional): The country code of the phone number. Defaults to an empty string.

        Returns:
            dict: A dictionary containing the user details.

        Note:
            - If either phone_number or country_code is not provided, the user details will not be fetched, and an empty dictionary will be returned.
        """
        request_data: dict = {
            "phone_number": phone_number,
            "country_code": country_code,
        }
        try:
            response: Response = requests.post(
                self.user_detail_phone_service_url,
                json=request_data,
                headers=self.headers,
            )
            response.raise_for_status()
            user_detail = self._prepare_response_body(response)
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as exc:
            logger.exception(f"Error getting user details from phone: {exc}")
            user_detail = {}
        return user_detail

    def _prepare_request(
        self, user_id: int = None, user_jid: int | uuid.UUID = None
    ) -> Dict[str, Any]:
        """
        Prepare the request body for sending to the user microservice.

        Args:
            user_id (int, optional): The user ID of the user. Defaults to None.
            user_jid (int or uuid.UUID, optional): The Jabber ID (JID) of the user. Defaults to None.

        Returns:
            dict: A dictionary containing the request data with the specified user ID and/or user JID.
        """

        request_data: Dict[str, Any] = {"user_id": ""}
        if user_id:
            request_data["user_id"] = user_id
        if user_jid:
            request_data["user_jid"] = user_jid

        return request_data

    def _prepare_response_body(self, response: Response) -> bytes:
        """
        Prepare the response body received from the user microservice.

        Args:
            response (Response): The HTTP response object from the user microservice.

        Returns:
            bytes: The response body as bytes.
        """
        result = response.json()
        return result


def user_notify_chat(
    message: str = "", message_from: str = "", to: str = "", xml: str = "", vhost: str = ""
) -> Dict:
    """
    Send a notification to a user using the user microservice's "notify_dm" API endpoint.

    Args:
        message (str, optional): The content of the message to be sent in the notification. Defaults to an empty string.
        message_from (str, optional): The sender of the notification. Defaults to an empty string.
        to (str, optional): The recipient of the notification. Defaults to an empty string.
        xml (str, optional): An optional XML payload to be included in the notification. Defaults to an empty string.
        vhost (str, optional): The virtual host for the notification. Defaults to an empty string.

    Returns:
        dict: A dictionary containing the response data received from the user microservice, if successful.
              If an error occurs during the request, an empty dictionary is returned.
    """
    result = {}
    request_data: dict = {
        "body": message,
        "from_user": message_from,
        "to": to,
        "xml": xml,
        "vhost": vhost,
    }
    base_url = settings.USER_MICROSERVICE_URL
    user_service_notify_dm = f"{base_url}api/users/notify_dm/"
    headers = {"X-Api-Key": settings.USER_MICROSERVICE_API_KEY}
    try:
        response: Response = requests.post(
            user_service_notify_dm,
            json=request_data,
            headers=headers,
        )
        response.raise_for_status()
        result = response.json
    except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
        result = {}
    finally:
        return result
