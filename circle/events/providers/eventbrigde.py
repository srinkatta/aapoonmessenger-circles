import json
from datetime import datetime
from typing import Any, Dict

import boto3
from loguru import logger

from circle.events.base import EventInterface
from circle_service import settings


class EventBridgeClient(EventInterface):
    def __init__(self) -> None:
        """
        Initializes the EventBridgeClient with settings from the configuration.
        """
        self.event_bus_name = settings.EVENT_BUS_NAME
        self.aws_access_key_id = settings.EVENT_AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = settings.EVENT_AWS_SECRET_ACCESS_KEY
        self.aws_region_name = settings.EVENT_AWS_REGION
        self.source = settings.EVENT_AWS_SOURCE
        self.detail_type = settings.EVENT_AWS_DETAIL_TYPE

        self.event_bridge_client = boto3.client(
            "events",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region_name,
        )

    def put_event(self, data: Dict[str, Any]) -> None:
        """
        Create an event in Event Bridge.

        Parameters:
        - data (Dict[str, Any]): The data to be included in the event.
        """
        try:
            logger.info("Event Creation")
            logger.info(data)
            response = self.event_bridge_client.put_events(
                Entries=[
                    {
                        "EventBusName": self.event_bus_name,
                        "Time": str(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
                        "Source": self.source,
                        "DetailType": self.detail_type,
                        "Detail": json.dumps(data),
                    }
                ],
            )
            logger.info("Event created successfully in event bridge.")
            logger.info(response)
        except Exception as err:
            logger.exception(
                f"Couldn't add event to events. Here's why: {err.response['Error']['Code']}: {err.response['Error']['Message']}"
            )
            raise
