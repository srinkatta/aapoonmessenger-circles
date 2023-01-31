import base64
import json
import uuid
from typing import (
    Any,
    Dict,
)

import requests
from requests import Response

from circle_service import settings


class User:
    def __init__(self):
        self.base_url = settings.USER_MICROSERVICE_URL
        self.user_detail_service_url = f"{self.base_url}api/users/user_details/"
        self.user_detail_phone_service_url = (
            f"{self.base_url}api/users/user_details/phone/"
        )
        self.headers = {"Authorization": settings.USER_MICROSERVICE_API_KEY}

    def details(self, user_id: int = None, user_jid=None) -> Dict:  # type: ignore
        request_data: dict = self._prepare_request(user_id, user_jid)
        user_detail = {}
        try:
            response: Response = requests.post(
                self.user_detail_service_url,
                json=request_data,
                headers=self.headers,
            )
            response.raise_for_status()
            user_detail = self._prepare_response_body(response)
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
            user_detail = {}
        finally:
            return user_detail

    def get_details_from_phone(self, phone_number: str = "") -> Dict:
        request_data: dict = {"phone_number": phone_number}
        user_detail = {}
        try:
            response: Response = requests.post(
                self.user_detail_phone_service_url,
                json=request_data,
                headers=self.headers,
            )
            response.raise_for_status()
            user_detail = self._prepare_response_body(response)
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
            user_detail = {}
        finally:
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
