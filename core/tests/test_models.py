"""
Tests for models.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model


class ModelTests(TestCase):
    """Test models."""

    def test_create_user_with_email_successful(self):
        """Test creating a user with an email is successful."""
        email = "test@example.com"
        password = "testpass123"
        user = get_user_model().objects.create_user(
            email=email,
            password=password,
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        """Test the email for a new user is normalized."""
        sample_emails = [
            ["test2@EXAmPLE.COM", "test2@example.com"],
            ["test3@ExamplE.com", "test3@example.com"],
        ]
        for email, expected_email in sample_emails:
            user = get_user_model().objects.create_user(email, "test123")
            self.assertEqual(user.email, expected_email)

    def test_new_user_without_email_raises_error(self):
        """Test creating user without email raises error."""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user(None, "test123")

    def test_create_superuser(self):
        """Test creating a new superuser."""
        user = get_user_model().objects.create_superuser(
            email="testsup@example.com",
            password="test123",
        )
        self.assertEqual(user.email, "testsup@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
