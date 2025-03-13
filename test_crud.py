import unittest
import asyncio
from app import app
from app.services import create_user, get_user_by_email

class UserTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_create_user(self):
        username = "testuser"
        email = "testuser@example.com"
        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(create_user(email, username))
        self.assertEqual(user.email, email)
        self.assertEqual(user.name, username)

    def test_get_user_by_email(self):
        email = "testuser@example.com"
        username = "testuser"
        loop = asyncio.get_event_
