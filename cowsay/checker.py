#!/usr/bin/env python3

import requests
import random
import string
import re
import logging
from bs4 import BeautifulSoup
from ctf_gameserver import checkerlib


class CowsayServiceChecker(checkerlib.BaseChecker):

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

            if "Login" not in response.text:
                logging.error("Login page doesn't contain expected content")
                return checkerlib.CheckResult.FAULTY

            # Check if we can access the register page
            response = requests.get(f"{base_url}/register", timeout=self.timeout)
            if response.status_code != 200:
                logging.error(
                    f"Register page not accessible: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.DOWN

            if "Register" not in response.text:
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

            # Test cowsay functionality
            cowsay_data = {"input_text": "Service Check Test"}

            response = session.post(
                f"{base_url}/dashboard", data=cowsay_data, timeout=self.timeout + 10
            )  # Allow extra time for cowsay execution
            if response.status_code != 200:
                logging.error(
                    f"Cowsay functionality broken: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.FAULTY

            # Check if cowsay output is present (be flexible due to potential vulnerability)
            if (
                "Service Check Test" not in response.text
                and "_" not in response.text
                and "Error:" not in response.text
            ):
                logging.error(
                    "Cowsay functionality appears broken - no expected output"
                )
                return checkerlib.CheckResult.FAULTY

            logging.info("Service health check passed")
            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during service check: {e}")
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

            # Check if registration was successful
            # The service redirects to login on successful registration
            if response.url and not response.url.endswith("/login"):
                # If we're not redirected to login, check for errors
                if "already exists" in response.text:
                    logging.error("Username collision during registration")
                    return checkerlib.CheckResult.FAULTY
                elif "error" in response.text.lower():
                    logging.error("Registration error occurred")
                    return checkerlib.CheckResult.FAULTY

            # Verify flag was placed by logging in and checking
            login_data = {"username": username, "password": password}
            response = session.post(
                f"{base_url}/login", data=login_data, timeout=self.timeout
            )

            if response.status_code != 200:
                logging.error("Cannot verify flag placement - login failed")
                return checkerlib.CheckResult.FAULTY

            if flag not in response.text:
                logging.error("Flag placement verification failed - flag not found")
                return checkerlib.CheckResult.FAULTY

            logging.info(f"Flag placed successfully for user {username} on tick {tick}")
            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during flag placement: {e}")
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
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            username = data["username"]
            password = data["password"]
            expected_flag = data["flag"]

            if expected_flag != flag:
                logging.error("Flag mismatch in stored data")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            base_url = self.get_base_url()
            session = requests.Session()

            # Login with stored credentials
            login_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/login", data=login_data, timeout=self.timeout
            )

            if response.status_code != 200:
                logging.error(f"Login failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Check if login was successful (should show dashboard)
            if "Welcome," not in response.text:
                logging.error("Login failed - not redirected to dashboard")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Check if flag is present in the message section
            if flag not in response.text:
                logging.error("Flag not found in user dashboard")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Verify the flag is in the correct location (message section)
            if "Your message:" not in response.text:
                logging.error("Message section not found in dashboard")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            logging.info(f"Flag check successful for user {username} on tick {tick}")
            return checkerlib.CheckResult.OK

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during flag check: {e}")
            return checkerlib.CheckResult.DOWN
        except Exception as e:
            logging.error(f"Unexpected error during flag check: {e}")
            return checkerlib.CheckResult.FLAG_NOT_FOUND


if __name__ == "__main__":
    checkerlib.run_check(CowsayServiceChecker)
