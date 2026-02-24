# accounts/serializers.py
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import User, UserSession,BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'display_name'
        ]

    def validate_username(self, v):
        v = v.lower()
        if User.objects.filter(username=v).exists():
            raise ValidationError('Username already taken.')
        return v

    def validate_email(self, v):
        v = v.lower()
        if User.objects.filter(email=v).exists():
            raise ValidationError('Email already in use.')
        return v

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save(update_fields=['password'])
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="username or email")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        ident = attrs.get('identifier', '').strip().lower()
        password = attrs.get('password')

        # find user by username OR email
        try:
            if '@' in ident:
                user = User.objects.get(email=ident)
            else:
                user = User.objects.get(username=ident)
        except User.DoesNotExist:
            raise ValidationError('Invalid credentials.')

        if user.is_locked():
            raise ValidationError('Account locked due to failed attempts. Try again later.')

        if not user.check_password(password):
            user.increment_failed_login()
            raise ValidationError('Invalid credentials.')

        if not user.is_active or user.is_banned:
            raise ValidationError('Account disabled.')

        # success
        user.reset_failed_login()
        attrs['user'] = user
        return attrs


class EmailVerifySerializer(serializers.Serializer):
    username = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        username = attrs['username'].lower()
        token = attrs['token']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError('User not found.')
        ok = user.verify_email(token)
        if not ok:
            raise ValidationError('Invalid or expired token.')
        attrs['user'] = user
        return attrs


class ResendEmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs['email'].lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError('No account with that email.')
        if user.email_verified:
            raise ValidationError('Email already verified.')
        attrs['user'] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs['email'].lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Do not leak existence; still act as success.
            attrs['user'] = None
            return attrs
        attrs['user'] = user
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    username = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

    def validate(self, attrs):
        username = attrs['username'].lower()
        token = attrs['token']
        new_pw = attrs['new_password']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError('Invalid token.')
        if not user.reset_password_with_token(token, new_pw):
            raise ValidationError('Invalid or expired token.')
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise ValidationError('Current password incorrect.')
        return attrs


    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'display_name','profile_picture','email_verified', 'date_joined', 'last_login']
        read_only_fields = ['id', 'email_verified', 'date_joined', 'last_login']


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ['id', 'user_agent', 'ip_address', 'created_at', 'last_seen_at', 'is_active', 'session_type', 'meta']
        read_only_fields = fields


# accounts/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(serializers.Serializer):
    identifier = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    
    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier")
        password = attrs.get("password")

        # Lookup user
        if '@' in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        else:
            user = User.objects.filter(username__iexact=identifier).first()

        if not user:
            # Optional: you can silently fail to avoid revealing valid usernames/emails
            raise serializers.ValidationError({"message": "Invalid credentials."})
        if user.is_locked():
            raise serializers.ValidationError("Account temporarily locked.")

        if not user.check_password(password):
            # Increment failed login counter
            user.increment_failed_login()
            remaining = max(0, 5 - user.failed_login_count)  # optional feedback
            raise serializers.ValidationError(f"Invalid credentials. {remaining} attempts left before lockout.")
        if not user.is_active:
            raise serializers.ValidationError("Account disabled.")
        if not user.email_verified:
            raise serializers.ValidationError("Email not verified.")
        

        # Generate JWT
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_id": str(user.id),
        }

from rest_framework_simplejwt.exceptions import TokenError
class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        refresh = attrs['refresh']

        # 1️⃣ Validate token
        try:
            token = RefreshToken(refresh)
        except TokenError:
            raise serializers.ValidationError("Invalid refresh token")

        # 2️⃣ Blacklist check (adjust for your setup)
        if BlacklistedToken.objects.filter(token=refresh).exists():
            raise serializers.ValidationError("Token is blacklisted")

        # 3️⃣ Return a dict containing both access & refresh
        return {
            "access": str(token.access_token),
            "refresh": str(token)
        }