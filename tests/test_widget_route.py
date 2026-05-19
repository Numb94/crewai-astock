import unittest
import sys
import os
from flask import Flask

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

class TestWidgetRoute(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_widget_route_exists(self):
        """Test if /widget route returns 200 OK (requires login)"""
        with self.app.session_transaction() as sess:
            sess['user_session_id'] = 'test_user'
            sess['username'] = 'test_user'
            
        response = self.app.get('/widget')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'QUANTUM WIDGET', response.data)

if __name__ == '__main__':
    unittest.main()
