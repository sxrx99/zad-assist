from django.test import TestCase, Client
from unittest.mock import patch
import requests
# use requests


class MicroserviceCommunicationTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("requests.post")
    def test_redirect_to_react_agent(self, mock_post):
        # Mock response from ReAct agent
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"result": "Processed: Test message"}

        # Send POST request to Django endpoint
        response = self.client.post(
            "/api/redirect/",
            data={"message": "Test message from Django"},
            content_type="application/json",
        )

        # Assert Django forwarded to ReAct and returned the correct response
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content, {"result": "Processed: Test message"}
        )

        # Assert Django actually called the ReAct agent endpoint
        mock_post.assert_called_with(
            "http://<ReAct-Agent-Service-Private-IP>:5000/process/",
            json={"message": "Test message from Django"},
        )