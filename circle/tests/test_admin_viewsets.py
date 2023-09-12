from django.test import TestCase
from rest_framework.test import APITestCase
from circle.models import *
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date
from rest_framework.authtoken.models import Token

class CircleListAPITestCase(APITestCase):
    def setUp(self):
        # Create a user for authentication
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        # Create circles for testing
        self.circle1 = Circle.objects.create(name='Circle 1')
        self.circle2 = Circle.objects.create(name='Circle 2')
        self.url = "/api/admin/circles/circle/list/"

    def test_circle_list_authenticated(self):
        client = APIClient()
        client.force_authenticate(user=self.user)  # Authenticate the client

        # Make a GET request to the CircleListAPI
        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Assuming the page_size is 100 in your API

    def test_circle_list_unauthenticated(self):
        client = APIClient()

        # Make a GET request to the CircleListAPI without authentication
        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_circle_list_filter_by_created_at(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Make a GET request to the CircleListAPI with a filter parameter
        response = client.get(self.url, {'created_at': '2023-01-01'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  

    def test_circle_list_pagination(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Create more circles to test pagination
        for _ in range(110):
            Circle.objects.create(name='Circle')

        # Make a GET request to the CircleListAPI
        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 100)  # Should return only the first page

class CircleExportCSVTestCase(APITestCase):
    def setUp(self):
        # Create a user for authentication
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.url = "/api/admin/circles/export/csv/"

    def test_circle_export_csv_authenticated(self):
        client = APIClient()
        client.force_authenticate(user=self.user)  # Authenticate the client

        # Make a GET request to the CircleExportCSV API
        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Disposition'), 'attachment; filename="circles_list.csv"')

        # Check the content type
        self.assertEqual(response.get('Content-Type'), 'text/csv')

        # You can also check the content of the CSV file in more detail if needed.

    def test_circle_export_csv_unauthenticated(self):
        client = APIClient()

        # Make a GET request to the CircleExportCSV API without authentication
        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class CircleDefaultConfigAPITestCase(TestCase):
    def setUp(self):
        # Create a user for authentication
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.url = "/api/admin/circles/circle/default/config/"

    def test_circle_default_config_authenticated(self):
        client = APIClient()
        client.force_authenticate(user=self.user)  # Authenticate the client

        # Make a GET request to the CircleDefaultConfigAPI
        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # You can further validate the response data as needed.
        # For example, check if the 'circle_type' field is present in the response.

        self.assertIn('circle_type', response.data)

    def test_circle_default_config_unauthenticated(self):
        client = APIClient()

        # Make a GET request to the CircleDefaultConfigAPI without authentication
        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)