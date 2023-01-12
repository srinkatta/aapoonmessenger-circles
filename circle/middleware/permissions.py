from rest_framework import permissions
from rest_framework.exceptions import APIException


class SessionExpired(APIException):
    status_code = 403
    default_detail = "Your session has expired. Please login again!"
    default_code = "session_expired"


class Authenticate(permissions.BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        if request.user_id and request.authenticated:
            return True
        else:
            raise SessionExpired()
