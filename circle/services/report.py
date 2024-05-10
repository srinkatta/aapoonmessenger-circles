import uuid
from typing import (
    Any,
    Dict,
    List,
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


class Report:
    """
    Utility class to interact with the user microservice and retrieve user details.

    Attributes:
        base_url (str): Base URL of the user microservice.
        headers (dict): Request headers including an authorization token.

    Methods:
        details(user_id, user_jid): Retrieve user details based on user ID or user JID.
        get_details_from_phone(phone_number, country_code): Retrieve user details based on phone number.

    Note:
        - This class is designed to interact with the user microservice API.
        - The methods 'details' and 'get_details_from_phone' use the 'requests' library to make HTTP requests.
    """

    def __init__(self):
        self.base_url = settings.REPORT_MICROSERVICE_URL

        self.headers = {"Authorization": settings.REPORT_MICROSERVICE_API_KEY}

    def report_info(self, circles: List[str | int]) -> Dict[str, Any]:  # type: ignore
        """
        Retrieve report details based on either the circle ID

        Args:
            circles (int, optional): the list of circles

        Returns:
            dict: A dictionary containing the reports details.

        """
        request_data: Dict[str, Any] = {"circles": circles}
        try:
            response: Response = requests.post(
                f"{self.base_url}api/reports/report/report-info/",
                json=request_data,
                headers=self.headers,
            )
            response.raise_for_status()
            report_detail = self._prepare_response_body(response)
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as exc:
            logger.exception(f"Error getting report details: {exc}")
            report_detail = {}
        return report_detail

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
