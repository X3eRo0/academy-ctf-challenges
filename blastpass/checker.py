#!/usr/bin/env python3

import requests
import random
import string
import logging
import sys
import os
from ctf_gameserver import checkerlib

# Add checker module to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from checker.api_test_suite import APITestSuite


class BlastpassChecker(checkerlib.BaseChecker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = 3333
        self.timeout = 30

    def generate_random_string(self, length=10):
        """Generate a random string for usernames and passwords"""
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def generate_random_password(self, length=12):
        """Generate a random password with special characters"""
        return "".join(
            random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=length)
        )

    def generate_vault_name(self):
        """Generate a random vault name"""
        return f"vault_{random.randint(1000, 9999)}"

    def get_base_url(self):
        """Get base URL for the service"""
        return f"http://{self.ip}:{self.port}"

    def check_service(self):
        """
        Check if the service is running and accessible using comprehensive API test suite
        """
        try:
            # Use API test suite for comprehensive testing
            api_tester = APITestSuite(self.ip, self.port, self.timeout)

            # Run all API tests
            results = api_tester.run_all_api_tests()

            # Clean up
            api_tester.cleanup()

            # Check if there was an error during setup
            if "error" in results:
                logging.error(f"API test suite error: {results['error']}")
                return checkerlib.CheckResult.DOWN

            # Count passed tests
            passed_tests = sum(1 for result in results.values() if result is True)
            total_tests = len(results)
            failed_tests = [
                test_name for test_name, result in results.items() if not result
            ]

            logging.info(f"API tests passed: {passed_tests}/{total_tests}")

            # Require ALL tests to pass
            if passed_tests == total_tests:
                logging.info("All API tests passed - service check successful")
                return checkerlib.CheckResult.OK
            else:
                logging.error(f"API tests failed: {failed_tests}")
                logging.error(
                    f"Failed tests: {total_tests - passed_tests}/{total_tests}"
                )
                return checkerlib.CheckResult.FAULTY

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during service check: {e}")
            return checkerlib.CheckResult.DOWN
        except Exception as e:
            logging.error(f"Unexpected error during service check: {e}")
            return checkerlib.CheckResult.DOWN

    def place_flag(self, tick):
        """
        Place flag in the service by creating a vault with flag as password entry
        """
        try:
            # Get the flag for this tick
            flag = checkerlib.get_flag(tick)

            base_url = self.get_base_url()
            session = requests.Session()

            # Generate random credentials
            username = f"user_{self.generate_random_string(8)}"
            password = self.generate_random_password()
            master_password = self.generate_random_password()
            vault_name = self.generate_vault_name()

            # Store credentials for later flag retrieval
            checkerlib.store_state(
                f"user_{tick}",
                {
                    "username": username,
                    "password": password,
                    "master_password": master_password,
                    "vault_name": vault_name,
                },
            )

            # Set flag ID for gameserver
            checkerlib.set_flagid(username)

            # Register user
            register_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/api/register", json=register_data, timeout=self.timeout
            )
            if response.status_code != 201:
                logging.error(f"Registration failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            # Login
            login_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/api/login", json=login_data, timeout=self.timeout
            )
            if response.status_code != 200:
                logging.error(f"Login failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            # Create vault with flag as password entry
            vault_data = {
                "name": vault_name,
                "master_password": master_password,
                "entries": [
                    {"url": "https://x3ero0.dev", "username": "admin", "password": flag}
                ],
            }

            response = session.post(
                f"{base_url}/api/vaults", json=vault_data, timeout=self.timeout
            )
            if response.status_code != 201:
                logging.error(f"Vault creation failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            vault_id = response.json().get("vault_id")
            if not vault_id:
                logging.error("No vault ID returned")
                return checkerlib.CheckResult.FAULTY

            # Update stored state with vault_id
            checkerlib.store_state(
                f"user_{tick}",
                {
                    "username": username,
                    "password": password,
                    "master_password": master_password,
                    "vault_name": vault_name,
                    "vault_id": vault_id,
                },
            )

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
            master_password = data["master_password"]
            vault_id = data["vault_id"]

            base_url = self.get_base_url()
            session = requests.Session()

            # Login with stored credentials
            login_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/api/login", json=login_data, timeout=self.timeout
            )
            if response.status_code != 200:
                logging.error(
                    f"Login failed during flag check: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            # Get vault entries
            response = session.get(
                f"{base_url}/api/vaults/{vault_id}/entries",
                params={"master_password": master_password},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                logging.error(
                    f"Failed to get vault entries: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            entries = response.json().get("entries", [])

            # Check if flag exists in vault
            flag_found = False
            for entry in entries:
                if (
                    entry.get("url") == "https://x3ero0.dev"
                    and entry.get("username") == "admin"
                    and entry.get("password") == flag
                ):
                    flag_found = True
                    break

            if not flag_found:
                logging.error("Flag not found in vault entries")
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
    checkerlib.run_check(BlastpassChecker)
