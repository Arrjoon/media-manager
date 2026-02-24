from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from django.db import close_old_connections
from asgiref.sync import sync_to_async

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        close_old_connections()

        # Lazy import ALL Django-dependent modules here
        from django.contrib.auth.models import AnonymousUser
        from rest_framework_simplejwt.tokens import AccessToken
        from accounts.models import User

        query_params = parse_qs(scope["query_string"].decode())
        token = query_params.get("token", [None])[0]

        if token:
            try:
                validated = AccessToken(token)
                user_id = validated["user_id"]
                scope["user"] = await self.get_user(user_id)
            except Exception as e:
                print("JWTAuthMiddleware error:", e)
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    @staticmethod
    async def get_user(user_id):
        from django.contrib.auth.models import AnonymousUser
        from accounts.models import User

        try:
            user = await sync_to_async(User.objects.get)(id=user_id)
            return user
        except User.DoesNotExist:
            return AnonymousUser()