from typing import List, Dict, Any

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import QuerySet, Q

from circle.middleware.permissions import Authenticate, ForbiddenAction
from circle.models import CircleSubscriberRole, Circle
from circle.services.report import Report
from circle.services.user import User


class DashboardView(APIView):
    """
    A simple APIView to demonstrate the usage of APIView.
    """

    permission_classes = (Authenticate,)

    def get(self, request):
        """
        Handle GET requests.
        """
        circles: QuerySet[Circle] = self.__get_associated_circles(user_id=request.user_id)
        subscribers = []
        circle_with_subscribers = {}
        if circles:
            descendants = circles[0].get_descendants()
            for descendant in descendants:
                subscribers_ids = list(descendant.subscribers.values_list("user_id", flat=True))
                circle_with_subscribers[descendant.id] = subscribers_ids
                subscribers.extend(subscribers_ids)

        subscribers = list(set(subscribers))

        user_details = {}
        if request.role.lower() in ["a ro", "ac ro"]:
            # if the role is ARO, then fetch all SO (one level below)
            user_details = self.__get_users_details(user_ids=subscribers, user_role="S O")
        elif request.role.lower() in ["deo", "pc ro"]:
            # if the role is DEO/PC RO, then fetch all ARO (one level below)
            user_details = self.__get_users_details(user_ids=subscribers, user_role="AC RO")
        else:
            raise ForbiddenAction()
        mapped_users, reports_payload = self.map_subscribers(user_details, circle_with_subscribers)

        report_details = self.get_report_details(circles=reports_payload)
        merged_data = [
            {**mapped_users[key], **report_details[str(key)]} for key in mapped_users.keys()
        ]

        return Response(merged_data)

    def __get_associated_circles(self, user_id) -> QuerySet[Circle]:
        final_circles = (
            CircleSubscriberRole.objects.select_related("circle")
            .select_related("role")
            .filter(user_id=user_id)
            .values_list("circle__id", flat=True)
        )

        circles = (
            Circle.objects.select_related("parent")
            .prefetch_related("topic")
            .filter(id__in=final_circles)
        )
        return circles

    def __get_users_details(self, user_ids: List[str | int], user_role: str):
        user_details = User().get_details_from_user_ids(user_ids=user_ids, user_role=user_role)
        return user_details

    def get_report_details(self, circles: List[str | int]):
        report_details = Report().report_info(circles=circles)
        return report_details

    def map_subscribers(self, user_details, circle_with_subscribers):
        mapped_dict = {}
        reports_payload = []
        for user in user_details:
            user_id = user["id"]
            # Find circle ID containing user_id
            for circle_id, subscriber_list in circle_with_subscribers.items():
                if user_id in subscriber_list:
                    user["circle_id"] = circle_id
                    mapped_dict[circle_id] = user
                    reports_payload.append(circle_id)
                    break

        return mapped_dict, reports_payload
