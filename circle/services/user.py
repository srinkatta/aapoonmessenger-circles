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
    def __init__(self):
        self.base_url = settings.USER_MICROSERVICE_URL
        self.user_detail_service_url = f"{self.base_url}api/users/user_details/"
        self.user_detail_phone_service_url = f"{self.base_url}api/users/user_details_phone/"
        self.headers = {"Authorization": settings.USER_MICROSERVICE_API_KEY}

    def details(self, user_id: int = None, user_jid=None) -> Dict:  # type: ignore
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
        """this prepare the request body"""

        request_data: Dict[str, Any] = {"user_id": ""}
        if user_id:
            request_data["user_id"] = user_id
        if user_jid:
            request_data["user_jid"] = user_jid

        return request_data

    def _prepare_response_body(self, response: Response) -> bytes:
        result = response.json()
        return result


def user_notify_chat(
    message: str = "", message_from: str = "", to: str = "", xml: str = "", vhost: str = ""
) -> Dict:
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
        result = response.json()
    except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
        result = {}
    return result
