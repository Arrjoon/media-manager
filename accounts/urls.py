# accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView
from .views import (
    RegisterView,
    LoginView,
    UsernameCheckView,
    RefreshTokenView,
    LogoutView,
    LogoutAllView,
    EmailVerifyView,
    ResendEmailVerificationView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    ProfileRetrieveUpdateView,
    SessionListView,
    SessionRevokeView,
)
app_name='accounts'

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('username/',UsernameCheckView.as_view(),name="check-username"),
    path('token/refresh/', RefreshTokenView.as_view(), name='token-refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token-verify'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('logout/all/', LogoutAllView.as_view(), name='logout-all'),
    
    # Email Verification
    path('verify-email/', EmailVerifyView.as_view(), name='verify-email'),
    path('resend-verification/', ResendEmailVerificationView.as_view(), name='resend-verification'),
    
    # Password Management
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('password/change/', ChangePasswordView.as_view(), name='password-change'),
    
    # Profile
    path('profile/', ProfileRetrieveUpdateView.as_view(), name='profile'),
    
    # Sessions
    path('sessions/', SessionListView.as_view(), name='session-list'),
    path('sessions/<uuid:session_id>/revoke/', SessionRevokeView.as_view(), name='session-revoke'),
]