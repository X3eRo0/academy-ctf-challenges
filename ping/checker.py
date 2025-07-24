#!/usr/bin/env python3

import requests
import random
import string
import re
import logging
from bs4 import BeautifulSoup
from ctf_gameserver import checkerlib


class PingServiceChecker(checkerlib.BaseChecker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = 5000
        self.timeout = 30

    def generate_random_string(self, length=10):
        """Generate a random string for usernames and messages"""
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def get_base_url(self):
        """Get base URL for the service"""
        return f"http://{self.ip}:{self.port}"

    def extract_csrf_token(self, response_text):
        """Extract CSRF token if present (not used in current service but good practice)"""
        # This service doesn't use CSRF tokens, but keeping for future enhancements
        return None

    def check_service(self):
        """
        Check if the service is running and accessible
        This verifies basic functionality without placing flags
        """
        try:
            base_url = self.get_base_url()

            # Check if service is accessible
            response = requests.get(f"{base_url}/", timeout=self.timeout)
            if response.status_code != 200:
                logging.error(f"Service not accessible: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            # Check if we can access the login page
            response = requests.get(f"{base_url}/login", timeout=self.timeout)
            if response.status_code != 200:
                logging.error(f"Login page not accessible: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            if "Login to Ping Service" not in response.text:
                logging.error("Login page doesn't contain expected content")
                return checkerlib.CheckResult.FAULTY

            # Check if we can access the register page
            response = requests.get(f"{base_url}/register", timeout=self.timeout)
            if response.status_code != 200:
                logging.error(
                    f"Register page not accessible: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.DOWN

            if "Register for Ping Service" not in response.text:
                logging.error("Register page doesn't contain expected content")
                return checkerlib.CheckResult.FAULTY

            # Test functionality with a temporary user
            session = requests.Session()

            # Generate test user credentials
            username = f"test_{self.generate_random_string(8)}"
            password = self.generate_random_string(12)
            test_message = "Test message for functionality check"

            # Test registration
            register_data = {
                "username": username,
                "password": password,
                "message": test_message,
            }

            response = session.post(
                f"{base_url}/register", data=register_data, timeout=self.timeout
            )
            if response.status_code != 200:
                logging.error(
                    f"Registration functionality broken: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.FAULTY

            # Test login
            login_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/login", data=login_data, timeout=self.timeout
            )
            if response.status_code != 200:
                logging.error(
                    f"Login functionality broken: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.FAULTY

            if "Welcome," not in response.text:
                logging.error("Login functionality broken - no welcome message")
                return checkerlib.CheckResult.FAULTY

            # Test ping functionality
            ping_data = {"ip": "8.8.8.8"}  # Google DNS - should be reliable

            response = session.post(
                f"{base_url}/dashboard", data=ping_data, timeout=self.timeout + 10
            )  # Allow extra time for ping
            if response.status_code != 200:
                logging.error(f"Ping functionality broken: HTTP {response.status_code}")
                return checkerlib.CheckResult.FAULTY

            logging.info("Service health check passed")
            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException as e:
            logging.error(f"3 Network error during service check: {e}")
            return checkerlib.CheckResult.DOWN
        except Exception as e:
            logging.error(f"Unexpected error during service check: {e}")
            return checkerlib.CheckResult.DOWN

    def place_flag(self, tick):
        """
        Place flag in the service by registering a user with flag as message
        """
        try:
            # Get the flag for this tick
            flag = checkerlib.get_flag(tick)

            base_url = self.get_base_url()
            session = requests.Session()

            # Generate random credentials
            username = f"user_{self.generate_random_string(8)}"
            password = self.generate_random_string(12)

            # Store credentials for later flag retrieval
            checkerlib.store_state(
                f"user_{tick}",
                {"username": username, "password": password, "flag": flag},
            )

            # Set flag ID for gameserver
            checkerlib.set_flagid(username)

            # Register user with flag as message
            register_data = {
                "username": username,
                "password": password,
                "message": flag,
            }

            response = session.post(
                f"{base_url}/register", data=register_data, timeout=self.timeout
            )

            if response.status_code != 200:
                logging.error(f"Registration failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            # Check if registration was successful (should redirect to login)
            if "Login to Ping Service" not in response.text and response.url.endswith(
                "/login"
            ):
                # If we're not redirected to login, registration might have failed
                if "already exists" in response.text:
                    logging.error("Username collision during registration")
                    return checkerlib.CheckResult.FAULTY
                elif "error" in response.text.lower():
                    logging.error("Registration error occurred")
                    return checkerlib.CheckResult.FAULTY

            logging.info(f"Flag placed successfully for user {username} on tick {tick}")
            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException as e:
            logging.error(f"2 Network error during flag placement: {e}")
            return checkerlib.CheckResult.DOWN
        except Exception as e:
            logging.error(f"Unexpected error during flag placement: {e}")
            return checkerlib.CheckResult.FAULTY

    def check_flag(self, tick):
        """
        Check if the previously placed flag is still accessible
        """
        try:
            # Get the flag for this tick
            flag = checkerlib.get_flag(tick)

            # Retrieve stored credentials
            data = checkerlib.load_state(f"user_{tick}")
            if not data:
                logging.error(f"No stored data found for flag check on tick {tick}")
                return checkerlib.CheckResult.FAULTY

            username = data["username"]
            password = data["password"]
            expected_flag = data["flag"]

            if expected_flag != flag:
                logging.error("Flag mismatch in stored data")
                return checkerlib.CheckResult.FAULTY

            base_url = self.get_base_url()
            session = requests.Session()

            # Login with stored credentials
            login_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/login", data=login_data, timeout=self.timeout
            )

            if response.status_code != 200:
                logging.error(f"Login failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            # Check if login was successful (should show dashboard)
            if "Welcome," not in response.text:
                logging.error("Login failed - not redirected to dashboard")
                return checkerlib.CheckResult.FAULTY

            # Check if flag is present in the message section
            if flag not in response.text:
                logging.error("Flag not found in user dashboard")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Verify the flag is in the correct location (message box)
            if "Your Message:" not in response.text:
                logging.error("Message section not found in dashboard")
                return checkerlib.CheckResult.FAULTY

            logging.info(f"Flag check successful for user {username} on tick {tick}")
            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException as e:
            logging.error(f"1 Network error during flag check: {e}")
            return checkerlib.CheckResult.DOWN
        except Exception as e:
            logging.error(f"Unexpected error during flag check: {e}")
            return checkerlib.CheckResult.FAULTY


if __name__ == "__main__":
    checkerlib.run_check(PingServiceChecker)
