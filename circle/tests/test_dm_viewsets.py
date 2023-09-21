from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, APIRequestFactory, force_authenticate
import unittest
from datetime import datetime
from django.contrib.auth.models import User  
from circle.models import ChatMessage
from unittest.mock import patch, Mock, MagicMock
from circle.api.direct_message.serializers import ChatMessageSerializer, ChatMessageFilterInputSerializer
from rest_framework.authtoken.models import Token
from circle.api.direct_message.viewsets import *
from django.db.models import QuerySet
from rest_framework.request import Request
from django.contrib.auth import get_user_model
from django.http import QueryDict



class XMPPMessageViewSetTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.url = "/api/circles/messages/"
        self.valid_data = {
            "message_id": "message1",
            "action": "like",
            # Include other required fields here
        }
        self.view = XMPPMessageViewSet()  
        self.message_id = "message1"

    def create_chat_message(self, message_id, action):
        return ChatMessage.objects.create(message_id=message_id, action=action)

    @patch('circle.models.ChatMessage.objects.filter')  # Mock the database query
    def test_list_xmpp_messages(self, mock_filter):
        # Create a valid instance of ChatMessage
        chat_message = ChatMessage(message_id='message1', action='like')
        
        # Mock the return value of the filter method
        mock_filter.return_value.aggregate.return_value = {
            'like': 1,
            'dislike': 0,
            'forward': 0,
            'reply': 0
        }

        # Mock the iterator() method of the filter result
        mock_filter.return_value.__iter__.return_value = [chat_message]

        # Send a GET request to list XMPP messages
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Expected data for message_id and like
        expected_message_id = "message1"
        expected_like = 1


        # Deserialize the response data using the serializer
        serializer = ChatMessageSerializer(chat_message)  # Pass the instance directly
        serialized_data = serializer.data

        # Remove the 'id' field from the serialized data
        serialized_data.pop('id', None)

        # Compare the message_id and like fields only
        self.assertEqual(serialized_data['message_id'], expected_message_id)
        self.assertEqual(serialized_data['like'], expected_like)

    @patch('circle.models.ChatMessage.objects.filter')  # Mock the database query
    def test_create_xmpp_message_success(self, mock_filter):
        # Mock the filter method to return an empty queryset
        mock_filter.return_value = ChatMessage.objects.none()

        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"success": True, "message": "Message stored successfully"})

        # Ensure the message was saved in the database
        chat_message = ChatMessage.objects.get(message_id=self.valid_data["message_id"])
        self.assertEqual(chat_message.action, self.valid_data["action"])
    
    @patch('circle.models.ChatMessage.objects.filter')  # Mock the database query
    def test_create_xmpp_message_duplicate_action(self, mock_filter):
        # Mock the filter method to return a non-empty queryset
        mock_filter.return_value = ChatMessage.objects.filter(message_id=self.valid_data["message_id"])

        response = self.client.post(self.url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Ensure the existing message with the same action is deleted
        chat_message = ChatMessage.objects.filter(message_id=self.valid_data["message_id"])
        self.assertTrue(chat_message.exists())

    def test_update_nonexistent_message(self):
        # Call the update_like_dislike method for a message that does not exist
        result = self.view.update_like_dislike(self.message_id, self.user.id, "like")

        # Assert that the method does not raise an exception (no message found)
        self.assertIsNone(result)

    def test_update_like_to_dislike(self):
        # Create a ChatMessage with the initial "like" action
        chat_message = ChatMessage.objects.create(
            message_id=self.message_id,
            action_by=self.user,
            action="dislike",
        )

        # Call the update_like_dislike method to change the action to "dislike"
        self.view.update_like_dislike(self.message_id, self.user.id, "dislike")

        # Retrieve the updated ChatMessage
        updated_message = ChatMessage.objects.get(message_id=self.message_id, action_by=self.user)

        # Assert that the action has been updated to "dislike"
        self.assertEqual(updated_message.action, "dislike")

        # Ensure that there are no other messages with the same action
        other_messages = ChatMessage.objects.filter(
            message_id=self.message_id, action_by=self.user
        ).exclude(id=updated_message.id)
        self.assertFalse(other_messages.exists())

    def test_update_dislike_to_like(self):
        # Create a ChatMessage with the initial "dislike" action
        chat_message = ChatMessage.objects.create(
            message_id=self.message_id,
            action_by=self.user,
            action="like",
        )

        # Call the update_like_dislike method to change the action to "like"
        self.view.update_like_dislike(self.message_id, self.user.id, "like")

        # Retrieve the updated ChatMessage
        updated_message = ChatMessage.objects.get(message_id=self.message_id, action_by=self.user)

        # Assert that the action has been updated to "like"
        self.assertEqual(updated_message.action, "like")
    
    @patch('circle.api.direct_message.serializers.ChatMessageSerializer', autospec=True)
    def test_retrieve_xmpp_message(self, MockChatMessageSerializer):
        user_model = get_user_model()

        # Create a mock user object for testing
        user2 = user_model.objects.create_user(
            username='testuser2',
            password='testpassword2',
            # Add other user data as needed...
        )

        message_data = {
            'message_id': 'message1',  # Add a 'message_id' key to the data
            'content': 'Hello, world!',
            'sender': user2,
            # ... other data ...
        }

        response = self.client.get(f'{self.url}message1/')  # Use the message_id in the URL
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create a dictionary with the expected response data
        expected_data = {
            'message': 'No message found for provided message_id',
            'success': False,
        }

        # Compare the response data with the expected data
        self.assertEqual(response.data, expected_data)

class XMPPMessageFilterViewSetTestCase(APITestCase):
    def create_chat_message(self, message_id, action):
        return ChatMessage.objects.create(message_id=message_id, action=action)

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.url = "/api/circles/get_messages/"  

    def test_filter_xmpp_messages_by_message_id(self):
        # Create ChatMessage objects with different message IDs
        self.create_chat_message(message_id="message1", action="like")
        self.create_chat_message(message_id="message2", action="dislike")
        self.create_chat_message(message_id="message3", action="forward")

        # Define the message IDs to filter by
        message_ids_to_filter = ["message1", "message2"]

        # Send a POST request to filter XMPP messages by message_id
        response = self.client.post(self.url, {"message_id": message_ids_to_filter}, format="json")

        # Check if the response status code is 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the 'message_id' values from the response data
        response_message_ids = [item["message_id"] for item in response.data]

        # Check that the response data contains the filtered message IDs
        expected_message_ids = ["message1", "message2"]
        self.assertEqual(response_message_ids, expected_message_ids)

    def test_filter_xmpp_messages_by_empty_message_id(self):
        # Create ChatMessage objects with different message IDs
        self.create_chat_message(message_id="message1", action="like")
        self.create_chat_message(message_id="message2", action="dislike")
        self.create_chat_message(message_id="message3", action="forward")

        # Send a POST request to filter XMPP messages with an empty message_id list
        response = self.client.post(self.url, {"message_id": []}, format="json")

        # Check if the response status code is 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that the response data is an empty list since no message IDs were provided
        self.assertEqual(response.data, [])

class TestArchiveChat(unittest.TestCase):

    def test_archive_chat_attributes(self):
        archived_chat_data = {
            "id": 1,
            "bare_peer": "user@example.com",
            "timestamp": datetime(2023, 9, 15, 12, 0),
            "xml": "<message>Hello, how are you?</message>",
            "username": "John Doe",
            "user_pic": "https://example.com/profile-pic.jpg",
        }

        archived_chat = ArchiveChat(**archived_chat_data)

        self.assertEqual(archived_chat.id, 1)
        self.assertEqual(archived_chat.bare_peer, "user@example.com")
        self.assertEqual(archived_chat.timestamp, datetime(2023, 9, 15, 12, 0))
        self.assertEqual(archived_chat.xml, "<message>Hello, how are you?</message>")
        self.assertEqual(archived_chat.username, "John Doe")
        self.assertEqual(archived_chat.user_pic, "https://example.com/profile-pic.jpg")

    def test_default_values(self):
        archived_chat = ArchiveChat()

        self.assertIsNone(archived_chat.id)
        self.assertIsNone(archived_chat.bare_peer)
        self.assertIsNone(archived_chat.timestamp)
        self.assertIsNone(archived_chat.xml)
        self.assertIsNone(archived_chat.username)
        self.assertIsNone(archived_chat.user_pic)

class XMPPChatViewSetTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.view = XMPPChatViewSet()
        self.factory = APIRequestFactory()
        self.url = "/api/circles/xmpp_chat/"

        self.client = APIClient()

        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_direct_query(self):
        # Define test data
        peer = "friend@example.com"
        username = "user@example.com"
        timestamp = 123456789
        length = 10

        # Create a request object
        request = self.factory.get(self.url, {'peer': peer, 'username': username})
        request = Request(request)  # Wrap the request with rest_framework's Request

        # Call the direct_query method
        view = XMPPChatViewSet()
        query = view.direct_query(request, str(timestamp), length)

        # Check specific parts of the query
        self.assertIn(f"peer='{peer}'", query)
        self.assertIn(f"username='{username}'", query)
        self.assertIn(f"timestamp<{timestamp}", query)
        self.assertIn(f"LIMIT {length};", query)

    def test_conference_query(self):
        # Define test data
        conference_id = "conference123"
        timestamp = 123456789
        length = 10

        # Create a Request object from rest_framework
        request = self.factory.get(self.url, {'conference_id': conference_id})
        request = Request(request)  # Wrap the request with rest_framework's Request

        # Call the conference_query method
        view = XMPPChatViewSet()
        query = view.conference_query(request, str(timestamp), length)  # Convert timestamp to a string

        # Check specific parts of the query
        self.assertIn(f"username='{conference_id}'", query)
        self.assertIn(f"timestamp<{timestamp}", query)
        self.assertIn(f"LIMIT {length};", query)

    
    def test_list_direct_messages(self):
        # Define test data
        timestamp = 123456789
        length = 10

        # Create a Request object from rest_framework
        request = self.factory.get(self.url, {'timestamp': timestamp, 'length': length, 'type': 'DIRECT'})
        request = Request(request)  # Wrap the request with rest_framework's Request

        # Mock the direct_query method to return a query
        view = XMPPChatViewSet()
        view.direct_query = lambda req, ts, ln: f"MockedDirectQuery_{ts}_{ln}"

        # Mock the fetch_archive_chat method to return sample data
        view.fetch_archive_chat = lambda q: [{'id': 1, 'timestamp': timestamp, 'xml': '<message>Sample Message</message>'}]

        # Call the list method
        response = view.list(request)

        # Check the response status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class NotifyRedirectViewSetTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)

        # Create a factory for making API requests
        self.factory = APIRequestFactory()

        self.client = APIClient()

        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.url = "/api/circles/notify_redirect/"

    def test_post_notification_direct_chat(self):
        # Define test data
        data = {
            "body": "Test message",
            "from_user": "sender@example.com",
            "to": "recipient@example.com",
            "xml": "<message>Test XML message</message>",
            "vhost": "example.com",  # Replace with your XMPP_HOST value
        }

        # Create a POST request
        request = self.factory.post(self.url, data, format='json')

        # Use your actual view and serializer class
        view = NotifyRedirectViewSet.as_view()
        response = view(request)

        # Check the response status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # You can also check the response data if needed
        self.assertEqual(response.data, {"message": "Notification sent."})

    def test_post_notification_conference_chat(self):
        # Define test data for a conference chat
        data = {
            "body": "Test message",
            "from_user": "sender@example.com",
            "to": "conference@example.com",
            "xml": "<message>Test XML message</message>",
            "vhost": "conference.example.com",  # Replace with your conference vhost
        }

        # Create a POST request
        request = self.factory.post(self.url, data, format='json')

        # Use your actual view and serializer class
        view = NotifyRedirectViewSet.as_view()
        response = view(request)

        # Check the response status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # You can also check the response data if needed
        self.assertEqual(response.data, {"message": "Notification sent."})

class MessageAbuseViewTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)

        # Create a factory for making API requests
        self.factory = APIRequestFactory()

        self.client = APIClient()

        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.url = "/api/circles/msg/abuse/"
        # Create a factory for making API requests
        self.factory = APIRequestFactory()

    def test_post_message_abuse_report(self):
        # Define test data
        data = {
            "message_ids": "1,2,3"  # Replace with the IDs of abusive messages to report
        }

        # Create a POST request
        request = self.factory.post(self.url, data, format='json')

        # Use your actual view and serializer class
        view = MessageAbuseView.as_view()
        response = view(request)

        # Check the response status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # You can also check the response data if needed
        self.assertEqual(response.data, {"message": "Mail sent Successfully"})