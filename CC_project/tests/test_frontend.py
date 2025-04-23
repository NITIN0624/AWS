import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to path so we can import the frontend module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions from app.py
import frontend.app as app

class TestFrontendApp(unittest.TestCase):
    @patch('requests.get')
    def test_get_functions(self, mock_get):
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "test_func", "language": "python", "code": "print('test')", "timeout": 30}
        ]
        mock_get.return_value = mock_response
        
        # Call the function
        result = app.get_functions()
        
        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "test_func")
        mock_get.assert_called_once_with(f"{app.API_BASE_URL}/functions/")
    
    @patch('requests.get')
    def test_get_functions_error(self, mock_get):
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response
        
        # Call the function (should return empty list on error)
        result = app.get_functions()
        
        # Assertions
        self.assertEqual(result, [])
    
    @patch('requests.post')
    def test_create_function(self, mock_post):
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Call the function
        result = app.create_function("test_func", "python", "print('test')", 30)
        
        # Assertions
        self.assertTrue(result)
        mock_post.assert_called_once()
        
    @patch('requests.post')
    def test_execute_function(self, mock_post):
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "status": "success",
                "stdout": "Hello, World!",
                "stderr": "",
                "metrics": {
                    "initialization_time_ms": 100,
                    "execution_time_ms": 50,
                    "total_time_ms": 150
                }
            }
        }
        mock_post.return_value = mock_response
        
        # Call the function
        result = app.execute_function("test_func", "docker", False)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["result"]["status"], "success")
        self.assertEqual(result["result"]["stdout"], "Hello, World!")
        mock_post.assert_called_once()

if __name__ == '__main__':
    unittest.main()
