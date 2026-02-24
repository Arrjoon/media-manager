# accounts/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import UserSession, BlacklistedToken
from .serializers import (
    RegisterSerializer,
    CustomTokenObtainPairSerializer,
    RefreshTokenSerializer,
    ProfileSerializer,
    SessionSerializer,
    EmailVerifySerializer,
    ResendEmailVerificationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
    ProfileSerializer,
    SessionSerializer
)
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserSession, BlacklistedToken

User = get_user_model()

# views.py
class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Ensure the request data uses 'identifier' instead of 'username'
        if 'username' in request.data:
            request.data['identifier'] = request.data.pop('username')
            
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            user = User.objects.get(id=response.data['user_id'])
            # Create session record
            session = UserSession.objects.create(
                user=user,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=request.META.get('REMOTE_ADDR', ''),
                meta={
                    'login_method': 'jwt',
                    'device': request.META.get('HTTP_USER_AGENT', '')[:255],
                    'login_with': 'email' if '@' in request.data.get('identifier') else 'username'
                }
            )
            
            # Enhance response
            response.data.update({
                'user': ProfileSerializer(user).data,
                'session': SessionSerializer(session).data
            })
            response.data.pop('user_id', None)

            # ✅ Set tokens in HttpOnly cookies
            access_token = response.data['access']
            refresh_token = response.data['refresh']

            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                secure=False,  
                samesite="Lax",
                max_age=60 * 5,
            )
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=False,
                samesite="Lax",
                max_age=60 * 60 * 24 * 7,
            )

        
        return response

    def _get_location_from_ip(self, ip_address):
        return None



class UsernameCheckView(APIView):
    def get(self, request, *args, **kwargs):
        username = request.GET.get("username")
        if User.objects.filter(username=username).exists():
            return Response({"message": "this username already present"})
        return Response({"message": "user with this username  not found"})



class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint that:
    1. Creates new user account
    2. Sends email verification
    3. Returns success message 
    """
    serializer_class = RegisterSerializer
    permission_classes = [] 

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # Send verification email
        send_email_verification(request, user)
        
        return Response({
            'detail': 'Registration successful. Please check your email to verify your account.',
            'user': {
                'email': user.email,
                'username': user.username,
                'email_verified': False
            }
        }, status=status.HTTP_201_CREATED)

class RefreshTokenView(TokenRefreshView):
    """
    Refresh JWT access token using refresh token stored in cookies
    """
    serializer_class = RefreshTokenSerializer

    def post(self, request, *args, **kwargs):
        # 1️⃣ Read refresh token from cookie
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found in cookies"},
                status=400
            )

        # 2️⃣ Inject refresh token into request.data
        request.data["refresh"] = refresh_token

        # 3️⃣ Call SimpleJWT's built-in refresh logic
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # 4️⃣ Get new access token
            access_token = response.data["access"]

            # 5️⃣ Update access_token cookie
            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                secure=False,
                samesite="Lax",
                max_age=60 * 5,  # 5 minutes
            )

            # 6️⃣ Update last_seen_at for the session (optional)
            if hasattr(request, 'session_id'):
                UserSession.objects.filter(
                    id=request.session_id
                ).update(last_seen_at=timezone.now())

        return response


class LogoutView(generics.GenericAPIView):
    """
    Logout from current session:
    1. Blacklists the refresh token
    2. Marks session as inactive
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RefreshTokenSerializer

    def post(self, request, *args, **kwargs):
        # 1️⃣ Try to get refresh token from cookie first
        refresh_token = request.COOKIES.get("refresh_token")

        # 2️⃣ If not in cookies, fallback to request body
        if not refresh_token:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            refresh_token = serializer.validated_data['refresh']

        # 3️⃣ Validate token
        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            return Response({"detail": "Invalid refresh token"}, status=status.HTTP_400_BAD_REQUEST)

        # 4️⃣ Blacklist token
        BlacklistedToken.objects.create(token=str(token))

        # 5️⃣ Mark session inactive
        if hasattr(request, "session_id"):
            UserSession.objects.filter(id=request.session_id, user=request.user).update(is_active=False)

        # 6️⃣ Optionally clear the cookies
        response = Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response


class LogoutAllView(generics.GenericAPIView):
    """
    Logout from all devices:
    1. Blacklists all user's refresh tokens
    2. Marks all sessions as inactive
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Get all unexpired refresh tokens for user
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
        from django.utils import timezone
        
        tokens = OutstandingToken.objects.filter(
            user=request.user,
            expires_at__gt=timezone.now()
        )
        
        # Blacklist all tokens
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token.token)
        
        # Mark all sessions as inactive
        UserSession.objects.filter(
            user=request.user,
            is_active=True
        ).update(is_active=False)
        
        return Response(
            {'detail': 'Successfully logged out from all devices.'},
            status=status.HTTP_200_OK
        )


class ActiveSessionsView(generics.ListAPIView):
    """
    List all active sessions for the current user
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SessionSerializer

    def get_queryset(self):
        return UserSession.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-last_seen_at')


class RevokeSessionView(generics.DestroyAPIView):
    """
    Revoke a specific session by ID
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SessionSerializer
    queryset = UserSession.objects.all()
    lookup_field = 'id'

    def perform_destroy(self, instance):
        # Don't actually delete, just mark as inactive
        instance.is_active = False
        instance.save()
        
        # Optionally blacklist associated token if available
        if instance.meta and 'token_id' in instance.meta:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
            try:
                token = OutstandingToken.objects.get(id=instance.meta['token_id'])
                BlacklistedToken.objects.get_or_create(token=token.token)
            except OutstandingToken.DoesNotExist:
                pass



from .utils import send_email_verification, send_password_reset

class EmailVerifyView(APIView):
    """
    Verify user's email with token
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailVerifySerializer

    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        # Generate new JWT tokens after verification
        refresh = RefreshToken.for_user(user)
        return Response({
            'detail': 'Email successfully verified.',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class ResendEmailVerificationView(APIView):
    """
    Resend email verification link
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = ResendEmailVerificationSerializer

    def post(self, request):
        serializer = ResendEmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        send_email_verification(request, user)
        return Response({'detail': 'Verification email resent.'})


class PasswordResetRequestView(APIView):
    """
    Initiate password reset process
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        if user:
            send_password_reset(request, user)
        
        return Response({
            'detail': 'If an account exists with this email, a password reset link has been sent.'
        })


class PasswordResetConfirmView(APIView):
    """
    Confirm password reset with token
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        # Generate new tokens after password change
        refresh = RefreshToken.for_user(user)
        return Response({
            'detail': 'Password successfully reset.',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class ChangePasswordView(APIView):
    """
    Change password for authenticated users
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate new tokens after password change
        refresh = RefreshToken.for_user(user)
        return Response({
            'detail': 'Password successfully changed.',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class ProfileRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """
    Get or update user profile
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProfileSerializer

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        # Handle email change verification
        user = self.request.user
        new_email = serializer.validated_data.get('email')
        
        if new_email and new_email.lower() != user.email.lower():
            user.email = new_email.lower()
            user.email_verified = False
            user.save()
            send_email_verification(self.request, user)
        
        serializer.save()


class SessionListView(generics.ListAPIView):
    """
    List all active sessions for current user
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SessionSerializer

    def get_queryset(self):
        return UserSession.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-last_seen_at')


class SessionRevokeView(generics.DestroyAPIView):
    """
    Revoke a specific session by ID
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SessionSerializer
    queryset = UserSession.objects.all()
    lookup_field = 'id'

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def perform_destroy(self, instance):
        # Mark session as inactive instead of deleting
        instance.is_active = False
        instance.save()
        
        # If this is the current session, blacklist the token
        if hasattr(self.request, 'session_id') and str(instance.id) == self.request.session_id:
            refresh_token = self.request.data.get('refresh')
            if refresh_token:
                BlacklistedToken.objects.create(token=refresh_token)

