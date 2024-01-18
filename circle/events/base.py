from abc import ABC, abstractmethod
from typing import Any, Dict


class EventInterface(ABC):
    @abstractmethod
    def put_event(self, data: Dict[str, Any]) -> None:
        """
        Abstract method to put an event into EventBridge.

        Parameters:
        - data (Dict[str, Any]): The data to be included in the event.
        """
        pass
