#!/usr/bin/env python3

import requests
import random
import string
import logging
from ctf_gameserver import checkerlib


class APITestSuite:
    def __init__(self, ip, port=3333, timeout=30):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{ip}:{port}"
        self.session = None
        self.credentials = None

    def generate_random_string(self, length=10):
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def generate_random_password(self, length=12):
        return "".join(
            random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=length)
        )

    def generate_vault_name(self):
        return f"vault_{random.randint(1000, 9999)}"

    def setup_credentials(self):
        username = f"user_{self.generate_random_string(random.randint(7, 10))}"
        password = self.generate_random_password()
        master_password = self.generate_random_password()

        self.credentials = {
            "username": username,
            "password": password,
            "master_password": master_password,
        }
        return True

    def run_all_api_tests(self):
        results = {}

        if not self.setup_credentials():
            return {"error": "Failed to setup credentials"}

        if not self.login_with_credentials():
            return {"error": "Failed to login"}

        tests = [
            ("health", self.test_health_endpoint),
            ("current_user", self.test_current_user_endpoint),
            ("list_vaults", self.test_list_vaults_endpoint),
            ("create_vault", self.test_create_vault_endpoint),
            ("get_vault_entries", self.test_get_vault_entries_endpoint),
            ("add_vault_entries", self.test_add_vault_entries_endpoint),
            ("validate_entry", self.test_validate_entry_endpoint),
            ("csv_import", self.test_csv_import_endpoint),
            ("download_vault", self.test_download_vault_endpoint),
            ("delete_vault", self.test_delete_vault_endpoint),
            ("logout", self.test_logout_endpoint),
            ("login_wrong_password", self.test_login_with_wrong_password),
            (
                "vault_access_wrong_master",
                self.test_vault_access_with_wrong_master_password,
            ),
            (
                "add_entries_wrong_master",
                self.test_add_entries_with_wrong_master_password,
            ),
        ]

        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
                logging.info(
                    f"API test {test_name}: {'PASS' if results[test_name] else 'FAIL'}"
                )
            except Exception as e:
                results[test_name] = False
                logging.error(f"API test {test_name} exception: {e}")

        return True

    def login_with_credentials(self):
        if not self.credentials:
            return False

        self.session = requests.Session()

        register_data = {
            "username": self.credentials["username"],
            "password": self.credentials["password"],
        }

        response = self.session.post(
            f"{self.base_url}/api/register", json=register_data, timeout=self.timeout
        )

        login_data = {
            "username": self.credentials["username"],
            "password": self.credentials["password"],
        }

        response = self.session.post(
            f"{self.base_url}/api/login", json=login_data, timeout=self.timeout
        )
        return response.status_code == 200

    def test_health_endpoint(self):
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=self.timeout)
            if response.status_code != 200:
                return False

            data = response.json()
            return data.get("status") == "healthy"
        except Exception as e:
            logging.error(f"Health endpoint test failed: {e}")
            return False

    def test_current_user_endpoint(self):
        try:
            response = self.session.get(f"{self.base_url}/api/me", timeout=self.timeout)
            if response.status_code != 200:
                return False

            data = response.json()
            return "user_id" in data and "username" in data
        except Exception as e:
            logging.error(f"Current user endpoint test failed: {e}")
            return False

    def test_logout_endpoint(self):
        """Test /api/logout endpoint"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/logout", timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Logout endpoint test failed: {e}")
            return False

    def test_login_with_wrong_password(self):
        try:
            temp_session = requests.Session()

            login_data = {
                "username": self.credentials["username"],
                "password": "wrong_password_123",
            }

            response = temp_session.post(
                f"{self.base_url}/api/login", json=login_data, timeout=self.timeout
            )

            success = response.status_code == 401
            if not success:
                logging.error(
                    f"Login with wrong password should fail but got: {response.status_code}"
                )

            temp_session.close()
            return success
        except Exception as e:
            logging.error(f"Wrong password login test failed: {e}")
            return False

    def test_vault_access_with_wrong_master_password(self):
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                if not self.test_create_vault_endpoint():
                    return False
                vault_id = self.credentials.get("test_vault_id")

            response = self.session.get(
                f"{self.base_url}/api/vaults/{vault_id}/entries",
                params={"master_password": "wrong_master_password_123"},
                timeout=self.timeout,
            )

            success = response.status_code in [400, 401]
            if not success:
                logging.error(
                    f"Vault access with wrong master password should fail but got: {response.status_code}"
                )

            return success
        except Exception as e:
            logging.error(f"Wrong master password test failed: {e}")
            return False

    def test_add_entries_with_wrong_master_password(self):
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                if not self.test_create_vault_endpoint():
                    return False
                vault_id = self.credentials.get("test_vault_id")

            entry_data = {
                "master_password": "wrong_master_password_123",
                "entries": [
                    {
                        "url": "https://test.com",
                        "username": "newuser",
                        "password": "newpass456",
                    }
                ],
            }

            response = self.session.post(
                f"{self.base_url}/api/vaults/{vault_id}/entries",
                json=entry_data,
                timeout=self.timeout,
            )

            success = response.status_code in [400, 401]
            if not success:
                logging.error(
                    f"Add entries with wrong master password should fail but got: {response.status_code}"
                )

            return success
        except Exception as e:
            logging.error(f"Wrong master password add entries test failed: {e}")
            return False

    def test_list_vaults_endpoint(self):
        try:
            response = self.session.get(
                f"{self.base_url}/api/vaults", timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            data = response.json()
            return "vaults" in data and isinstance(data["vaults"], list)
        except Exception as e:
            logging.error(f"List vaults endpoint test failed: {e}")
            return False

    def test_create_vault_endpoint(self):
        try:
            vault_name = self.generate_vault_name()
            vault_data = {
                "name": vault_name,
                "master_password": self.credentials["master_password"],
                "entries": [
                    {
                        "url": "https://example.com",
                        "username": "testuser",
                        "password": "testpass123",
                    }
                ],
            }

            response = self.session.post(
                f"{self.base_url}/api/vaults", json=vault_data, timeout=self.timeout
            )
            if response.status_code != 201:
                return False

            data = response.json()
            vault_id = data.get("vault_id")
            if vault_id:
                self.credentials["test_vault_id"] = vault_id
                self.credentials["test_vault_name"] = vault_name

            return "vault_id" in data
        except Exception as e:
            logging.error(f"Create vault endpoint test failed: {e}")
            return False

    def test_get_vault_entries_endpoint(self):
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                if not self.test_create_vault_endpoint():
                    return False
                vault_id = self.credentials.get("test_vault_id")

            response = self.session.get(
                f"{self.base_url}/api/vaults/{vault_id}/entries",
                params={"master_password": self.credentials["master_password"]},
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return False

            data = response.json()
            return "entries" in data and isinstance(data["entries"], list)
        except Exception as e:
            logging.error(f"Get vault entries endpoint test failed: {e}")
            return False

    def test_add_vault_entries_endpoint(self):
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                # Create a vault first
                if not self.test_create_vault_endpoint():
                    return False
                vault_id = self.credentials.get("test_vault_id")

            entry_data = {
                "master_password": self.credentials["master_password"],
                "entries": [
                    {
                        "url": "https://test.com",
                        "username": "newuser",
                        "password": "newpass456",
                    }
                ],
            }

            response = self.session.post(
                f"{self.base_url}/api/vaults/{vault_id}/entries",
                json=entry_data,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return False

            data = response.json()
            return "entries_added" in data
        except Exception as e:
            logging.error(f"Add vault entries endpoint test failed: {e}")
            return False

    def test_validate_entry_endpoint(self):
        try:
            entry_data = {
                "url": "https://example.com",
                "username": "testuser",
                "password": "testpass",
            }

            response = self.session.post(
                f"{self.base_url}/api/validate-entry",
                json=entry_data,
                timeout=self.timeout,
            )
            if response.status_code != 200:
                return False

            data = response.json()
            return "valid" in data
        except Exception as e:
            logging.error(f"Validate entry endpoint test failed: {e}")
            return False

    def test_csv_import_endpoint(self):
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                if not self.test_create_vault_endpoint():
                    return False
                vault_id = self.credentials.get("test_vault_id")

            csv_content = "https://csv.example.com,csvuser,csvpass123"

            files = {"file": ("test.csv", csv_content, "text/csv")}
            data = {"master_password": self.credentials["master_password"]}

            response = self.session.post(
                f"{self.base_url}/api/vaults/{vault_id}/import",
                files=files,
                data=data,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return False

            result = response.json()
            return "entries_imported" in result
        except Exception as e:
            logging.error(f"CSV import endpoint test failed: {e}")
            return False

    def test_download_vault_endpoint(self):
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                # Create a vault first
                if not self.test_create_vault_endpoint():
                    return False
                vault_id = self.credentials.get("test_vault_id")

            download_data = {"comment": "Test download"}

            response = self.session.post(
                f"{self.base_url}/api/vaults/{vault_id}/download",
                json=download_data,
                timeout=self.timeout,
            )

            return response.status_code == 200 and len(response.content) > 0
        except Exception as e:
            logging.error(f"Download vault endpoint test failed: {e}")
            return False

    def test_delete_vault_endpoint(self):
        try:
            vault_name = self.generate_vault_name()
            vault_data = {
                "name": vault_name,
                "master_password": self.credentials["master_password"],
                "entries": [],
            }

            response = self.session.post(
                f"{self.base_url}/api/vaults", json=vault_data, timeout=self.timeout
            )
            if response.status_code != 201:
                return False

            vault_id = response.json().get("vault_id")
            if not vault_id:
                return False

            response = self.session.delete(
                f"{self.base_url}/api/vaults/{vault_id}", timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Delete vault endpoint test failed: {e}")
            return False

    def run_all_api_tests(self):
        """Run all API endpoint tests"""
        results = {}

        if not self.setup_credentials():
            return {"error": "Failed to setup credentials"}

        if not self.login_with_credentials():
            return {"error": "Failed to login"}

        tests = [
            ("health", self.test_health_endpoint),
            ("current_user", self.test_current_user_endpoint),
            ("list_vaults", self.test_list_vaults_endpoint),
            ("create_vault", self.test_create_vault_endpoint),
            ("get_vault_entries", self.test_get_vault_entries_endpoint),
            ("add_vault_entries", self.test_add_vault_entries_endpoint),
            ("validate_entry", self.test_validate_entry_endpoint),
            ("csv_import", self.test_csv_import_endpoint),
            ("download_vault", self.test_download_vault_endpoint),
            ("delete_vault", self.test_delete_vault_endpoint),
            ("logout", self.test_logout_endpoint),
            # Security tests - these should fail with wrong credentials
            ("login_wrong_password", self.test_login_with_wrong_password),
            (
                "vault_access_wrong_master",
                self.test_vault_access_with_wrong_master_password,
            ),
            (
                "add_entries_wrong_master",
                self.test_add_entries_with_wrong_master_password,
            ),
        ]

        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                results[test_name] = False
                logging.error(f"API test {test_name} exception: {e}")

        passed = sum(1 for result in results.values() if result)
        total = len(results)
        logging.info(f"API test suite completed: {passed}/{total} tests passed")
        return results

    def cleanup(self):
        """Cleanup session"""
        if self.session:
            try:
                self.session.close()
            except:
                pass
