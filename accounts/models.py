# accounts/models.py
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.core.validators import RegexValidator, MinLengthValidator


USERNAME_REGEX = r'^[A-Za-z0-9_\.]+$' 


class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("The username must be set")
        if not email:
            raise ValueError("The email must be set")
        

        username = username.lower()
        email = self.normalize_email(email)

        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # create a unusable password for social-only accounts
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model:
    - username: unique handle (like Reddit)
    - email: unique for recovery and social linking
    - email_verified: whether email was confirmed
    - social accounts in SocialAccount model
    - optional MFA (TOTP) fields
    - token fields for email verification / password reset
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(USERNAME_REGEX, "Enter a valid username."),
            MinLengthValidator(3),
        ],
        help_text="Unique username/handle (lowercased)."
    )
    email = models.EmailField(unique=True, db_index=True)
    display_name = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.ImageField(blank=True, null=True,upload_to='mdia/profile_pictures/')
    is_admin        = models.BooleanField(default=False)
    # account flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    # timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    # tokens for flows
    email_verification_token = models.CharField(max_length=128, blank=True, null=True)
    email_verification_expiry = models.DateTimeField(blank=True, null=True)
    password_reset_token = models.CharField(max_length=128, blank=True, null=True)
    password_reset_expiry = models.DateTimeField(blank=True, null=True)

    # MFA (TOTP)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.CharField(max_length=512, blank=True, null=True) 
    # login protection
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ("-date_joined",)
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
        ]
    def token(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


    def __str__(self):
        return self.username

    # ---------------------------
    # token helper methods
    # ---------------------------
    def set_email_verification(self, hours=24):
        token = uuid.uuid4().hex
        self.email_verification_token = token
        self.email_verification_expiry = timezone.now() + timedelta(hours=hours)
        # do not mark email_verified here
        self.save(update_fields=["email_verification_token", "email_verification_expiry"])
        return token

    def verify_email(self, token):
        if not token:
            return False
        if (
            self.email_verification_token == token
            and self.email_verification_expiry
            and self.email_verification_expiry > timezone.now()
        ):
            self.email_verified = True
            self.email_verification_token = None
            self.email_verification_expiry = None
            self.save(update_fields=["email_verified", "email_verification_token", "email_verification_expiry"])
            return True
        return False

    def set_password_reset(self, hours=1):
        token = uuid.uuid4().hex
        self.password_reset_token = token
        self.password_reset_expiry = timezone.now() + timedelta(hours=hours)
        self.save(update_fields=["password_reset_token", "password_reset_expiry"])
        return token

    def reset_password_with_token(self, token, new_password):
        if (
            self.password_reset_token == token
            and self.password_reset_expiry
            and self.password_reset_expiry > timezone.now()
        ):
            self.set_password(new_password)
            self.password_reset_token = None
            self.password_reset_expiry = None
            # save will also update password field
            self.save()
            return True
        return False

    # ---------------------------
    # account lock helpers
    # ---------------------------
    def increment_failed_login(self, lock_threshold=5, lock_minutes=15):
        self.failed_login_count += 1
        if self.failed_login_count >= lock_threshold:
            self.locked_until = timezone.now() + timedelta(minutes=lock_minutes)
        self.save(update_fields=["failed_login_count", "locked_until"])

    def reset_failed_login(self):
        self.failed_login_count = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_count", "locked_until"])

    def is_locked(self):
        return self.locked_until and self.locked_until > timezone.now()




class BlacklistedToken(models.Model):
    token = models.CharField(max_length=500, unique=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Blacklisted token {self.token}"

class SocialAccount(models.Model):
    """
    Stores external provider link (facebook/google/etc.) for a user.
    Use provider + provider_id to uniquely identify external account.
    """
    PROVIDER_CHOICES = [
        ("facebook", "Facebook"),
        ("google", "Google"),
        ("apple", "Apple"),
        ("twitter", "Twitter"),
        # extend as needed
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="social_accounts", on_delete=models.CASCADE)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    provider_id = models.CharField(max_length=255, db_index=True)
    extra_data = models.JSONField(blank=True, null=True) 
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "provider_id")
        indexes = [models.Index(fields=["provider", "provider_id"])]

    def __str__(self):
        return f"{self.provider}:{self.provider_id} -> {self.user}"


class UserSession(models.Model):
    """
    Optional: track active sessions/device tokens for the user.
    Useful to show a UI to "Logout from all devices" and revoke sessions.
    For JWT you can store refresh token jti here and revoke by blacklisting.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sessions", on_delete=models.CASCADE)
    user_agent = models.CharField(max_length=512, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    session_type = models.CharField(max_length=50, default="web")  # web, mobile, api
    meta = models.JSONField(blank=True, null=True)  # any other useful metadata (device id, jti, etc.)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "is_active"])]
