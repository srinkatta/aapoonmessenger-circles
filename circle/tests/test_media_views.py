from rest_framework.test import (
    APIClient, 
    APITestCase, 
    APIRequestFactory, 
    force_authenticate,
)
from rest_framework import status
from circle.api.media_views.viewsets import (
    ChatAudioUploadViewSet,
    ChatDocumentsUploadViewSet,
    ChatImageUploadViewSet,
    ChatVideoUploadViewSet,
    GroupImageUploadViewSet,
)
from circle.api.media_views.s3uploadserializer import S3UploadPolicySerializer  
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User  
from unittest.mock import Mock
from unittest.mock import patch
from rest_framework.response import Response
from rest_framework.request import Request


class GroupImageUploadViewSetTestCase(APITestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', password='testpassword')

        # Create a token for the user
        self.token, _ = Token.objects.get_or_create(user=self.user)

        # Authenticate the client with the token
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")

        # Define the URL for the view
        self.url = "/api/circles/s3groupimageparams/" 

    @patch('circle.api.media_views.viewsets.GroupImageUploadViewSet.list')
    def test_list_endpoint(self, mock_list):
        # Mock the behavior of the list method
        mock_list.return_value = Response({
            'key': 'your_mocked_key',
            'content_type': 'image/jpeg'
        })

        # Authenticate the test user
        self.client.force_authenticate(user=self.user)

        # Make a GET request to the list endpoint
        response = self.client.get(self.url)  

        # Check if the response status code is 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if the response data has the expected keys
        self.assertIn('key', response.data)
        self.assertIn('content_type', response.data)

class ChatImageUploadViewSetTestCase(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', password='testpassword')

        # # Create a token for the user
        # self.token, _ = Token.objects.get_or_create(user=self.user)

        # # Authenticate the client with the token
        # self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")

        # Define the URL for the view
        self.url = "/api/circles/s3chatimageparams/"  
    def test_list_endpoint(self):
        # Create a request factory
        factory = APIRequestFactory()

        # Create a request object with a 'unique_id' attribute
        request = factory.get(self.url)  
        request.user = self.user
        request.unique_id = '123456789'  # Add a 'unique_id' attribute

        # Create an instance of the view
        view = ChatImageUploadViewSet.as_view({'get': 'list'})

        # Call the view with the custom request object
        response = view(request)

        # Check if the response status code is 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if the response data has the expected keys
        self.assertIn('key', response.data)

class ChatVideoUploadViewSetTestCase(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        self.url = "/api/circles/s3chatvideoparams/"

    def test_list_endpoint(self):
        # Create a request factory
        factory = APIRequestFactory()

        # Create a request object with a 'unique_id' attribute
        request = factory.get(self.url)  # Replace with your actual API endpoint
        request.user = self.user
        request.unique_id = '123456789'  # Add a 'unique_id' attribute

        # Create an instance of the view
        view = ChatVideoUploadViewSet.as_view({'get': 'list'})

        # Call the view with the custom request object
        response = view(request)

        # Check if the response status code is 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if the 'key' exists in the response data
        self.assertIn('key', response.data)

class ChatDocumentsUploadViewSetTestCase(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        self.url = "/api/circles/s3chatdocsparams/"

    def test_list_endpoint(self):
        # Create a request factory
        factory = APIRequestFactory()

        # Create a request object with a 'unique_id' attribute
        request = factory.get(self.url)  # Replace with your actual API endpoint
        request.user = self.user
        request.unique_id = '123456789'  # Add a 'unique_id' attribute

        # Create an instance of the view
        view = ChatDocumentsUploadViewSet.as_view({'get': 'list'})

        # Call the view with the custom request object
        response = view(request)

        # Check if the response status code is 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if the 'key' exists in the response data
        self.assertIn('key', response.data)

class ChatAudioUploadViewSetTestCase(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        self.url = "/api/circles/s3chataudioparams/"

    def test_list_endpoint(self):
        # Create a request factory
        factory = APIRequestFactory()

        # Create a request object with a 'unique_id' attribute
        request = factory.get(self.url)  # Replace with your actual API endpoint
        request.user = self.user
        request.unique_id = '123456789'  # Add a 'unique_id' attribute

        # Create an instance of the view
        view = ChatAudioUploadViewSet.as_view({'get': 'list'})

        # Call the view with the custom request object
        response = view(request)

        # Check if the response status code is 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if the 'key' exists in the response data
        self.assertIn('key', response.data)
