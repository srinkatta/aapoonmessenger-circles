import csv

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from circle.middleware.permissions import Authenticate
from circle import models as circle_models
from circle.api.admin import serializers as admin_serializers


class CircleListAPI(APIView, PageNumberPagination):
    """
    API to list all circles and filter based on created_at
    """

    serializers_class = admin_serializers.CircleListSerializer
    permission_classes = (Authenticate,)
    page_size = 100

    def get(self, request):
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
    Export Circle list into a CSV file
    """

    permission_classes = (Authenticate,)

    def get(self):
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
    API to get Circle default configurations & permissions
    """

    permission_classes = (Authenticate,)
    serializer_class = admin_serializers.CircleDefaultConfSerializer

    def get(self, request):
        default_config = {
            "circle_type": circle_models.Circle._meta.get_field("circle_type").default,
        }
        serializer = self.serializer_class(data=default_config)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
