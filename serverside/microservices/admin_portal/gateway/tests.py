from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status


class GatewayTestCase(SimpleTestCase):
    """
    Efficient test suite for API Gateway endpoints.
    Uses SimpleTestCase to skip database setup/teardown overhead.
    """

    def test_api_root(self):
        """Test API root endpoint returns 200 with valid service listing."""
        # Resolve URL by name (maintains compatibility if base path changes)
        # Falls back to hardcoded path if reverse() isn't available in your URL config
        try:
            url = reverse('api-root')
        except Exception:
            url = '/api/'

        response = self.client.get(url)

        # 1. Validate HTTP status
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 2. Parse JSON once and cache for assertions
        data = response.json()

        # 3. Validate expected structure
        self.assertIn('services', data)
        self.assertIsInstance(data['services'], list)
        self.assertGreater(len(data['services']), 0, "Expected at least one registered microservice")