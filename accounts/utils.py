
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def absolute_url(request, path: str) -> str:
    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host() if request else 'localhost:8000'
    return f"{scheme}://{host}{path}"


def send_email_verification(request, user):
    token = user.set_email_verification(hours=24)
    path = reverse('accounts:verify-email') + f"?token={token}&username={user.username}"
    url = absolute_url(request, path)
    subject = 'Verify your email'
    message = f"Hello {user.username},\n\nClick to verify: {url}\nThis link expires in 24 hours."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def send_password_reset(request, user):
    token = user.set_password_reset(hours=1)
    path = reverse('accounts:password-reset-confirm') + f"?token={token}&username={user.username}"
    url = absolute_url(request, path)
    subject = 'Password reset'
    message = f"Hello {user.username},\n\nReset your password here: {url}\nThis link expires in 1 hour."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])