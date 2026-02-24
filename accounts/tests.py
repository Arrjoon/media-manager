from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from django.test import TestCase

User = get_user_model()

class JWTAuthTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="pass1234"
        )

    def test_token_auth_flow(self):
        response = self.client.post("/api/auth/token/", {
            "username": "testuser",
            "password": "pass1234"
        }, format='json')
        self.assertEqual(response.status_code, 200)
        access_token = response.data["access"]
        print(f"\nAccess Token: {access_token}")

        protected = self.client.get(
            "/api/auth/protected/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )
        self.assertEqual(protected.status_code, 200)

class SimpleTest(TestCase):
    def test_example(self):
        self.assertEqual(1 + 1, 2)


from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from accounts.models import User


class UserModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123"
        )

    def test_create_user(self):
        self.assertEqual(self.user.username, "testuser")
        self.assertEqual(self.user.email, "testuser@example.com")
        self.assertTrue(self.user.check_password("password123"))
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass"
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

    def test_username_lowercase(self):
        user = User.objects.create_user(
            username="TESTCASE",
            email="case@example.com",
            password="pass"
        )
        self.assertEqual(user.username, "testcase")  # should be saved lowercase

    def test_email_verification_token_flow(self):
        token = self.user.set_email_verification(hours=1)
        self.assertIsNotNone(token)
        self.assertFalse(self.user.email_verified)
        self.assertTrue(self.user.email_verification_expiry > timezone.now())
        # Verify correct token
        result = self.user.verify_email(token)
        self.assertTrue(result)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertIsNone(self.user.email_verification_token)

    def test_reset_password_with_token(self):
        token = self.user.set_password_reset(hours=1)
        self.assertIsNotNone(token)
        # Wrong token
        self.assertFalse(self.user.reset_password_with_token("wrongtoken", "newpass"))
        # Correct token
        result = self.user.reset_password_with_token(token, "newpass")
        self.assertTrue(result)
        self.assertTrue(self.user.check_password("newpass"))

    def test_failed_login_lock(self):
        # Initially not locked
        self.assertFalse(self.user.is_locked())
        # Increment failures to reach threshold
        for _ in range(5):
            self.user.increment_failed_login(lock_threshold=5, lock_minutes=1)
        self.assertTrue(self.user.is_locked())
        # Reset failures and lock
        self.user.reset_failed_login()
        self.assertFalse(self.user.is_locked())

    def test_username_validation(self):
        # Username with invalid chars should raise ValidationError on full_clean
        user = User(username="Invalid Username!", email="valid@example.com")
        with self.assertRaises(ValidationError):
            user.full_clean()  # runs all model validations including validators

    def test_unique_username_email(self):
        # Trying to create user with existing username or email should raise error
        with self.assertRaises(Exception):  # could be IntegrityError or ValidationError depending on test db
            User.objects.create_user(username="testuser", email="newemail@example.com", password="pass")
        with self.assertRaises(Exception):
            User.objects.create_user(username="newuser", email="testuser@example.com", password="pass")
