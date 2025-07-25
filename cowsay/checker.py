#!/usr/bin/env python3

import requests
import random
import string
import re
from ctf_gameserver import checkerlib
import hashlib
import time


class CowsayChecker(checkerlib.BaseChecker):
    """
    Checker for the Cowsay CTF service

    This checker implements the required functionality:
    1. check_service: Verify basic service health
    2. place_flag: Place flag in user message during registration
    3. check_flag: Verify placed flag is accessible
    4. Verify intentional functionality (register, login, cowsay)
    """

    def __init__(self, tick, team, service, ip):
        super().__init__(tick, team, service, ip)
        self.port = 5000
        self.base_url = f"http://{ip}:{self.port}"
        self.session = requests.Session()
        self.session.timeout = 10

    def generate_random_string(self, length=12):
        """Generate random string for usernames/passwords"""
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def generate_username(self):
        """Generate unique username for this tick"""
        return f"user_{self.tick}_{self.generate_random_string(8)}"

    def register_user(self, username, password, message):
        """Register a new user"""
        try:
            # Get registration page first
            resp = self.session.get(f"{self.base_url}/register")
            if resp.status_code != 200:
                return False, "Registration page not accessible"

            # Submit registration form
            data = {"username": username, "password": password, "message": message}

            resp = self.session.post(
                f"{self.base_url}/register", data=data, allow_redirects=False
            )

            # Should redirect to login page on success
            if resp.status_code == 302 and "/login" in resp.headers.get("Location", ""):
                return True, "Registration successful"
            elif resp.status_code == 200:
                # Check if there's an error message in the response
                if "already exists" in resp.text:
                    return False, "Username already exists"
                else:
                    return False, "Registration failed with unknown error"
            else:
                return False, f"Unexpected response code: {resp.status_code}"

        except requests.RequestException as e:
            return False, f"Network error during registration: {str(e)}"

    def login_user(self, username, password):
        """Login with credentials"""
        try:
            # Get login page first
            resp = self.session.get(f"{self.base_url}/login")
            if resp.status_code != 200:
                return False, "Login page not accessible"

            # Submit login form
            data = {"username": username, "password": password}

            resp = self.session.post(
                f"{self.base_url}/login", data=data, allow_redirects=False
            )

            # Should redirect to dashboard on success
            if resp.status_code == 302 and (
                "/" in resp.headers.get("Location", "")
                or "/dashboard" in resp.headers.get("Location", "")
            ):
                return True, "Login successful"
            elif resp.status_code == 200:
                if "Invalid username or password" in resp.text:
                    return False, "Invalid credentials"
                else:
                    return False, "Login failed with unknown error"
            else:
                return False, f"Unexpected response code: {resp.status_code}"

        except requests.RequestException as e:
            return False, f"Network error during login: {str(e)}"

    def test_cowsay(self, test_input="Hello World"):
        """Test cowsay functionality"""
        try:
            # Get dashboard
            resp = self.session.get(f"{self.base_url}/dashboard")
            if resp.status_code != 200:
                return False, "Dashboard not accessible"

            # Submit cowsay form
            data = {"input_text": test_input}
            resp = self.session.post(f"{self.base_url}/dashboard", data=data)

            if resp.status_code != 200:
                return False, f"Cowsay request failed with status {resp.status_code}"

            # Check if output contains expected cowsay format
            if "< " + test_input + " >" in resp.text or test_input in resp.text:
                return True, "Cowsay working correctly"
            else:
                return False, "Cowsay output not found or incorrect"

        except requests.RequestException as e:
            return False, f"Network error during cowsay test: {str(e)}"

    def check_message_displayed(self, expected_message):
        """Check if user message is displayed on dashboard"""
        try:
            resp = self.session.get(f"{self.base_url}/dashboard")
            if resp.status_code != 200:
                return False, "Dashboard not accessible"

            # Look for the message in the user info section
            if expected_message in resp.text:
                return True, "Message found on dashboard"
            else:
                return False, "Message not found on dashboard"

        except requests.RequestException as e:
            return False, f"Network error checking message: {str(e)}"

    def check_service(self):
        """
        Check if the service is running and functional
        Tests basic functionality: registration, login, cowsay
        """
        try:
            # Test if service is reachable
            resp = self.session.get(self.base_url)
            if resp.status_code != 200:
                return checkerlib.CheckResult.DOWN

            # Generate test credentials
            username = self.generate_username()
            password = self.generate_random_string(16)
            test_message = f"test_message_{self.generate_random_string(8)}"

            # Test registration
            success, msg = self.register_user(username, password, test_message)
            if not success:
                self.logger.warning(f"Registration failed: {msg}")
                return checkerlib.CheckResult.FAULTY

            # Test login
            success, msg = self.login_user(username, password)
            if not success:
                self.logger.warning(f"Login failed: {msg}")
                return checkerlib.CheckResult.FAULTY

            # Test cowsay functionality
            success, msg = self.test_cowsay("Service Check")
            if not success:
                self.logger.warning(f"Cowsay failed: {msg}")
                return checkerlib.CheckResult.FAULTY

            # Test message display
            success, msg = self.check_message_displayed(test_message)
            if not success:
                self.logger.warning(f"Message display failed: {msg}")
                return checkerlib.CheckResult.FAULTY

            return checkerlib.CheckResult.OK

        except Exception as e:
            self.logger.error(f"Service check failed: {str(e)}")
            return checkerlib.CheckResult.DOWN

    def place_flag(self, flag):
        """
        Place flag by registering a user with flag as message
        Store credentials for later flag checking
        """
        try:
            # Generate credentials for flag user
            username = f"flag_{self.tick}_{hashlib.md5(flag.encode()).hexdigest()[:8]}"
            password = self.generate_random_string(20)

            # Register user with flag as message
            success, msg = self.register_user(username, password, flag)
            if not success:
                self.logger.error(f"Flag placement failed: {msg}")
                return checkerlib.CheckResult.FAULTY

            # Store credentials for flag checking
            self.store_credentials(username, password, flag)

            # Verify flag was placed correctly by logging in and checking
            success, msg = self.login_user(username, password)
            if not success:
                self.logger.error(f"Flag verification login failed: {msg}")
                return checkerlib.CheckResult.FAULTY

            success, msg = self.check_message_displayed(flag)
            if not success:
                self.logger.error(f"Flag not found after placement: {msg}")
                return checkerlib.CheckResult.FAULTY

            return checkerlib.CheckResult.OK

        except Exception as e:
            self.logger.error(f"Flag placement error: {str(e)}")
            return checkerlib.CheckResult.FAULTY

    def check_flag(self, flag):
        """
        Check if previously placed flag is still accessible
        """
        try:
            # Retrieve stored credentials
            username, password, stored_flag = self.retrieve_credentials()

            if not username or stored_flag != flag:
                self.logger.error("Stored credentials not found or flag mismatch")
                return checkerlib.CheckResult.FAULTY

            # Create new session for flag checking
            flag_session = requests.Session()
            flag_session.timeout = 10

            # Login with stored credentials
            data = {"username": username, "password": password}

            resp = flag_session.post(
                f"{self.base_url}/login", data=data, allow_redirects=False
            )

            if resp.status_code != 302:
                self.logger.error("Flag user login failed")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Check dashboard for flag
            resp = flag_session.get(f"{self.base_url}/dashboard")
            if resp.status_code != 200:
                self.logger.error("Flag user dashboard not accessible")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Verify flag is displayed
            if flag in resp.text:
                return checkerlib.CheckResult.OK
            else:
                self.logger.error("Flag not found in dashboard")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

        except Exception as e:
            self.logger.error(f"Flag check error: {str(e)}")
            return checkerlib.CheckResult.FLAG_NOT_FOUND

    def store_credentials(self, username, password, flag):
        """Store credentials for flag checking"""
        # Use the checker's built-in storage mechanism
        self.store_state(
            f"flag_user_{self.tick}",
            {"username": username, "password": password, "flag": flag},
        )

    def retrieve_credentials(self):
        """Retrieve stored credentials"""
        try:
            stored_data = self.retrieve_state(f"flag_user_{self.tick}")
            if stored_data:
                return (
                    stored_data["username"],
                    stored_data["password"],
                    stored_data["flag"],
                )
            else:
                return None, None, None
        except:
            return None, None, None


if __name__ == "__main__":
    checkerlib.run_check(CowsayChecker)
