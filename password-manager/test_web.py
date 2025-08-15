#!/usr/bin/env python3
"""
Simple test script to verify the web interface works
"""
import requests
import os

BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:5000').replace('/api', '')

def test_web_interface():
    """Test web interface functionality"""
    print("=== Password Manager Web Interface Tests ===\n")
    
    try:
        # Test home page
        print("Testing home page...")
        response = requests.get(f"{BASE_URL}/")
        print(f"Home page response: {response.status_code}")
        
        # Test login page
        print("Testing login page...")
        response = requests.get(f"{BASE_URL}/login")
        print(f"Login page response: {response.status_code}")
        
        # Test registration page
        print("Testing registration page...")
        response = requests.get(f"{BASE_URL}/register")
        print(f"Registration page response: {response.status_code}")
        
        # Test registration submission
        print("Testing user registration...")
            response = requests.post(f"{BASE_URL}/register", data={
        'username': 'webuser',
        'password': 'testpass123',
        'confirm_password': 'testpass123'
    }, allow_redirects=False)
        print(f"Registration POST response: {response.status_code}")
        
        print("\n=== Web tests completed ===")
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Make sure the Flask app is running.")
    except Exception as e:
        print(f"Test error: {e}")

if __name__ == "__main__":
    test_web_interface()
