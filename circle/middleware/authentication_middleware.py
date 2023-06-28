from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from circle.services.user import User


class ExtraJWTAuthentication(JWTAuthentication):
    def _extract_token(self, auth_token):
        if not auth_token:
            return None
        auth_token = auth_token.replace("Bearer ", "").replace("JWT ", "")
        try:
            decoded_token = AccessToken(auth_token)
            return decoded_token
        except TokenError as exc:
            raise exceptions.AuthenticationFailed(exc)

    def _set_user_details(self, request):
        try:
            user_service = User()
            user = user_service.details(user_id=request.user_id)
            request.first_name = user.get("first_name", "")
            request.last_name = user.get("last_name", "")
            request.name = user.get("name", "")
            request.jid = user.get("jid", "")
            request.unique_id = user.get("unique_id", "")
            request.authenticated = True
        except Exception as exc:
            print(exc)

    def authenticate(self, request):
        auth_token = request.META.get("HTTP_AUTHORIZATION")
        decoded_token = self._extract_token(auth_token)
        if decoded_token:
            request.user_id = decoded_token["user_id"]
            request.authenticated = False
            self._set_user_details(request)
            return None, decoded_token
        return None
