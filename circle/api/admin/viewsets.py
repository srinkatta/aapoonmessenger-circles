import csv

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from circle.middleware.permissions import Authenticate
from circle import models as circle_models
from circle.api.admin import serializers as admin_serializers
from circle.api.utils import GenericPagination


class CircleListAPI(APIView, GenericPagination):
    """
    API View to list all circles and filter based on created_at.

    This view allows users to retrieve a list of all circles and provides filtering based on the creation date.

    Query Parameters:
        created_at (str, optional): Filters the circles based on the creation date. Expected format: "YYYY-MM-DD".

    Returns:
        Response: A paginated response containing a list of circles with details.
    """

    serializers_class = admin_serializers.CircleListSerializer
    permission_classes = (Authenticate,)
    page_size = 100

    def get(self, request):
        """
        Get a list of circles.

        This method retrieves a list of all circles or filters the circles based on the creation date.

        Returns:
           Response: A paginated response containing a list of circles with details.
        """
        if request.query_params.get("created_at"):
            circles = circle_models.Circle.objects.filter(
                created_at__gte=request.query_params.get("created_at")
            ).order_by("-id")
        else:
            circles = circle_models.Circle.objects.all().order_by("-id")
        pagination = self.paginate_queryset(circles, request)
        serializer = self.serializers_class(pagination, many=True)
        return self.get_paginated_response(serializer.data)


class CircleExportCSV(APIView):
    """
    API View to export the Circle list into a CSV file.

    This view allows users to export the list of circles into a CSV file. The exported CSV file will contain details
    such as circle ID, name, owner, circle users count, created date, hierarchy, and total children count.

    Returns:
        HttpResponse: An HTTP response with the CSV file containing the circle data.
    """

    permission_classes = (Authenticate,)

    def get(self):
        """
        Export Circle list into a CSV file.

        This method exports the list of circles into a CSV file. The exported CSV file will contain details
        such as circle ID, name, owner, circle users count, created date, hierarchy, and total children count.

        Returns:
            HttpResponse: An HTTP response with the CSV file containing the circle data.
        """
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="circles_list.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "name",
                "owner",
                "circle_users_count",
                "created_at",
                "hierarchy",
                "total_children_count",
            ]
        )
        circles = circle_models.Circle.objects.all().order_by("-id")
        for circle in circles:
            writer.writerow(
                [
                    circle.id,
                    circle.name,
                    circle.owner_id,
                    circle.circle_users_count,
                    circle.created_at,
                    circle.hierarchy,
                    circle.total_children_count,
                ]
            )
        return response


class CircleDefaultConfigAPI(APIView):
    """
    API View to get Circle default configurations and permissions.

    This view allows users to retrieve the default configurations and permissions for creating a Circle.
    It returns the default circle type.

    Returns:
        Response: A response containing the default circle configuration and permissions.
    """

    permission_classes = (Authenticate,)
    serializer_class = admin_serializers.CircleDefaultConfSerializer

    def get(self, request):
        """
        Get Circle default configurations and permissions.

        This method retrieves the default configurations and permissions for creating a Circle.
        It returns the default circle type.

        Returns:
            Response: A response containing the default circle configuration and permissions.
        """
        default_config = {
            "circle_type": circle_models.Circle._meta.get_field("circle_type").default,
        }
        serializer = self.serializer_class(data=default_config)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
