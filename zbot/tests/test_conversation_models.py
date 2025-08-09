"""
Tests for models.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model


from zbot import models


class ModelTests(TestCase):
    """Test models."""
    def test_create_conversation(self):
            """Test creating a new conversation."""
            user = get_user_model().objects.create_user(
                email="ismail@gmail.com",
                password="test123",
            )
            conversation = models.Conversation.objects.create(
                name="test conversation01",
                title="test-conversation",
                user=user,
            )
            self.assertIs(conversation.user, user)
            self.assertEqual(conversation.name, "test conversation01")

        def test_create_text_message(self):
            """Test creating a new text message."""
            user = get_user_model().objects.create_user(
                email="ismail@gmail.com",
                password="test123",
            )
            conversation = models.Conversation.objects.create(
                name="test conversation01",
                title="test-conversation",
                user=user,
            )
            text_message = models.TextMessage.objects.create(
                conversation=conversation,
                text="test text message",
            )
            self.assertIs(text_message.conversation, conversation)
            self.assertEqual(text_message.text, "test text message")
            
        def test_create_image_message(self):
            """Test creating a new image message."""
            user = get_user_model().objects.create_user(
                email="ismail@gmail.com",
                password="test123",
            )
            conversation = models.Conversation.objects.create(
                name="test conversation01",
                title="test-conversation",
                user=user,
            )
            image_message = models.ImageMessage.objects.create(
                conversation=conversation,
                metadata="test.jpg",
            )
            self.assertIs(image_message.conversation, conversation)
            self.assertEqual(image_message.metadata, "test.jpg")
