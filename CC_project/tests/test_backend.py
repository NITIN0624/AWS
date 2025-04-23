import sys
import os
import pytest
import fastapi
import starlette
import httpx

print(f"FastAPI version: {fastapi.__version__}")
print(f"Starlette version: {starlette.__version__}")
print(f"HTTPX version: {httpx.__version__}")

# Now try the original approach, without context manager
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_list_functions(client):
    response = client.get("/functions/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_function(client):
    function_data = {
        "name": "test_function",
        "language": "python",
        "code": "print('hello world')",
        "timeout": 30
    }
    # First try to delete if it exists (cleanup)
    client.delete(f"/functions/{function_data['name']}")
    
    # Now create
    response = client.post(
        "/functions/",
        json=function_data
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Function saved"
    
    # Clean up
    client.delete(f"/functions/{function_data['name']}")

def test_get_function(client):
    # Create a function first
    function_data = {
        "name": "test_get_function",
        "language": "python",
        "code": "print('hello world')",
        "timeout": 30
    }
    client.post("/functions/", json=function_data)
    
    # Now get it
    response = client.get(f"/functions/{function_data['name']}")
    assert response.status_code == 200
    assert response.json()["name"] == function_data["name"]
    
    # Clean up
    client.delete(f"/functions/{function_data['name']}")

def test_update_function(client):
    # Create a function first
    function_data = {
        "name": "test_update_function",
        "language": "python",
        "code": "print('hello world')",
        "timeout": 30
    }
    client.post("/functions/", json=function_data)
    
    # Update it - include the name field here
    update_data = {
        "name": "test_update_function",  # Add this line
        "language": "python",
        "code": "print('updated')",
        "timeout": 60
    }
    response = client.put(
        f"/functions/{function_data['name']}",
        json=update_data
    )
    assert response.status_code == 200
    
    # Verify update
    get_response = client.get(f"/functions/{function_data['name']}")
    assert get_response.json()["code"] == update_data["code"]
    
    # Clean up
    client.delete(f"/functions/{function_data['name']}")

def test_delete_function(client):
    # Create a function first
    function_data = {
        "name": "test_delete_function",
        "language": "python",
        "code": "print('hello world')",
        "timeout": 30
    }
    client.post("/functions/", json=function_data)
    
    # Delete it
    response = client.delete(f"/functions/{function_data['name']}")
    assert response.status_code == 200
    
    # Verify deletion
    get_response = client.get(f"/functions/{function_data['name']}")
    assert get_response.status_code == 404
