from rest_framework import status
from rest_framework.test import APIClient
import pytest

@pytest.fixture
def create_text_message(api_client):
    def do_create_text_message(text_message):
        return api_client.post('/store/textMessages/', text_message)
    return do_create_text_message

@pytest.mark.django_db
class TestCreateTextMessage:
    def test_if_user_anonymous_returns_401():
        # Arrange

        # Act
        text_message = APIClient()
        response = text_message.post(
            "/zbot/textMessages/",
            {"text": "test"},
            format="json",
        )
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
