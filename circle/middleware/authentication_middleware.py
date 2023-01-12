from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from circle.services.user import User


class ExtraJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        auth_token = request.META.get("HTTP_AUTHORIZATION")
        if not auth_token:
            return None

        try:
            auth_token = auth_token.replace("Bearer ", "")
            auth_token = auth_token.replace("JWT ", "")
            decoded_token = AccessToken(auth_token)
            # set user details in request
            request.user_id = decoded_token["user_id"]
            request.authenticated = False
            try:
                user_service = User()
                user = user_service.details(user_id=request.user_id)
                request.first_name = user.get("first_name")
                request.last_name = user.get("last_name")
                request.jid = user.get("jid")
                request.authenticated = True
            except Exception as exc:
                print(exc)

            return None, decoded_token
        except TokenError as exc:
            raise exceptions.AuthenticationFailed(exc)
