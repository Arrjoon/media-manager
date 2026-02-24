from rest_framework_simplejwt.authentication import JWTAuthentication

class CookieBasedJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get("access_token")
        if access_token:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
        return super().authenticate(request)

class CookieBasedJWTRefreshAuthentication(JWTAuthentication):
    def authenticate(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            request.data["refresh"] = refresh_token
        return super().authenticate(request)
