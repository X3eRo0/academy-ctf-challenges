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
from checker.web_test_suite import WebTestSuite


class BlastpassChecker(checkerlib.BaseChecker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = 3333
        self.timeout = 30

    def generate_random_string(self, length=10):
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def generate_random_password(self, length=12):
        return "".join(
            random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=length)
        )

    def generate_vault_name(self):
        return f"vault_{random.randint(1000, 9999)}"

    def get_base_url(self):
        return f"http://{self.ip}:{self.port}"

    def check_service(self):
        try:
            use_api_tests = random.choice([True, False])

            if use_api_tests:
                logging.info("Selected API test suite for service check")
                tester = APITestSuite(self.ip, self.port, self.timeout)
                results = tester.run_all_api_tests()
                test_type = "API"
            else:
                logging.info("Selected Web frontend test suite for service check")
                tester = WebTestSuite(self.ip, self.port, self.timeout)
                results = tester.run_all_web_tests()
                test_type = "Web"
            tester.cleanup()
            if "error" in results:
                logging.error(f"{test_type} test suite error: {results['error']}")
                return checkerlib.CheckResult.DOWN

            passed_tests = sum(1 for result in results.values() if result is True)
            total_tests = len(results)
            failed_tests = [
                test_name for test_name, result in results.items() if not result
            ]

            logging.info(f"{test_type} tests passed: {passed_tests}/{total_tests}")

            if passed_tests == total_tests:
                logging.info(f"All {test_type} tests passed - service check successful")
                return checkerlib.CheckResult.OK
            else:
                logging.error(f"{test_type} tests failed: {failed_tests}")
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
        try:
            flag = checkerlib.get_flag(tick)
            base_url = self.get_base_url()
            session = requests.Session()

            username = f"user_{self.generate_random_string(8)}"
            password = self.generate_random_password()
            master_password = self.generate_random_password()
            vault_name = self.generate_vault_name()

            checkerlib.store_state(
                f"user_{tick}",
                {
                    "username": username,
                    "password": password,
                    "master_password": master_password,
                    "vault_name": vault_name,
                },
            )

            checkerlib.set_flagid(username)
            register_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/api/register", json=register_data, timeout=self.timeout
            )
            if response.status_code != 201:
                logging.error(f"Registration failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

            login_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/api/login", json=login_data, timeout=self.timeout
            )
            if response.status_code != 200:
                logging.error(f"Login failed: HTTP {response.status_code}")
                return checkerlib.CheckResult.DOWN

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

            checkerlib.store_state(
                f"{tick}",
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
        try:
            flag = checkerlib.get_flag(tick)
            data = checkerlib.load_state(f"{tick}")
            if not data:
                logging.error(f"No stored data found for flag check on tick {tick}")
                return checkerlib.CheckResult.FLAG_NOT_FOUND

            username = data["username"]
            password = data["password"]
            master_password = data["master_password"]
            vault_id = data["vault_id"]

            base_url = self.get_base_url()
            session = requests.Session()

            login_data = {"username": username, "password": password}

            response = session.post(
                f"{base_url}/api/login", json=login_data, timeout=self.timeout
            )
            if response.status_code != 200:
                logging.error(
                    f"Login failed during flag check: HTTP {response.status_code}"
                )
                return checkerlib.CheckResult.FLAG_NOT_FOUND

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
