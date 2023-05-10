from django.urls import path
from circle.api.admin import viewsets as admin_viewsets

urlpatterns = [
    path(
        "circle/list/",
        admin_viewsets.CircleListAPI.as_view(),
        name="circle-list-filter",
    ),
    path(
        "export/csv/",
        admin_viewsets.CircleExportCSV.as_view(),
        name="circle-export-csv",
    ),
    path(
        "circle-default-config/",
        admin_viewsets.CircleDefaultConfigAPI.as_view(),
        name="circle-default-configurations-permissions",
    ),
]
