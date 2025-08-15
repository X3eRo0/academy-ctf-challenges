#!/usr/bin/env python3
"""
Simple test script to verify the password manager backend works
"""
import requests
import json
import os

BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:5000/api')

def test_registration():
    """Test user registration"""
    print("Testing user registration...")
    response = requests.post(f"{BASE_URL}/register", json={
        "username": "testuser",
        "password": "testpassword123"
    })
    print(f"Registration response: {response.status_code} - {response.json()}")
    return response.status_code == 201

def test_login():
    """Test user login"""
    print("Testing user login...")
    response = requests.post(f"{BASE_URL}/login", json={
        "username": "testuser", 
        "password": "testpassword123"
    })
    print(f"Login response: {response.status_code} - {response.json()}")
    return response.status_code == 200

def test_vault_creation(session):
    """Test vault creation"""
    print("Testing vault creation...")
    response = session.post(f"{BASE_URL}/vaults", json={
        "name": "My Test Vault",
        "master_password": "testpassword123",
        "entries": [
            {
                "url": "https://example.com",
                "username": "user1", 
                "password": "pass123"
            },
            {
                "url": "https://google.com",
                "username": "user2",
                "password": "pass456"
            }
        ]
    })
    print(f"Vault creation response: {response.status_code} - {response.json()}")
    if response.status_code == 201:
        return response.json()['vault_id']
    return None

def test_vault_retrieval(session, vault_id):
    """Test vault entry retrieval"""
    print("Testing vault entry retrieval...")
    response = session.get(f"{BASE_URL}/vaults/{vault_id}/entries?master_password=testpassword123")
    print(f"Vault retrieval response: {response.status_code} - {response.json()}")
    return response.status_code == 200

def test_entry_validation():
    """Test entry validation"""
    print("Testing entry validation...")
    
    # Valid entry
    response = requests.post(f"{BASE_URL}/validate-entry", json={
        "url": "https://test.com",
        "username": "validuser",
        "password": "validpass123"
    })
    print(f"Valid entry response: {response.status_code} - {response.json()}")
    
    # Invalid entry (special characters)
    response = requests.post(f"{BASE_URL}/validate-entry", json={
        "url": "https://test.com", 
        "username": "invalid@user",
        "password": "invalid!pass"
    })
    print(f"Invalid entry response: {response.status_code} - {response.json()}")

def run_tests():
    """Run all tests"""
    print("=== Password Manager Backend Tests ===\n")
    
    # Test health check
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health check: {response.status_code} - {response.json()}\n")
    
    # Test registration and login
    if not test_registration():
        print("Registration failed!")
        return
    
    # Create session for authenticated requests
    session = requests.Session()
    if not test_login():
        print("Login failed!")
        return
    
    # Login to get session cookie
    response = session.post(f"{BASE_URL}/login", json={
        "username": "testuser",
        "password": "testpassword123"
    })
    
    # Test vault operations
    vault_id = test_vault_creation(session)
    if vault_id:
        test_vault_retrieval(session, vault_id)
    
    # Test validation
    test_entry_validation()
    
    print("\n=== Tests completed ===")

if __name__ == "__main__":
    try:
        run_tests()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Make sure the Flask app is running on http://localhost:5000")
    except Exception as e:
        print(f"Test error: {e}")
