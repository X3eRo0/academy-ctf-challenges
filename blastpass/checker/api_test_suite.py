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

    def setup_credentials(self):
        """Setup fresh credentials for testing"""
        # Always create new credentials for service checks
        username = f"test_{self.generate_random_string(8)}"
        password = self.generate_random_password()
        master_password = self.generate_random_password()

        self.credentials = {
            "username": username,
            "password": password,
            "master_password": master_password,
        }

    def run_all_api_tests(self):
        """Run all API endpoint tests"""
        results = {}

        # Setup credentials
        if not self.setup_credentials():
            return {"error": "Failed to setup credentials"}

        # Login
        if not self.login_with_credentials():
            return {"error": "Failed to login"}

        # Run all tests
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
        """Login using stored credentials"""
        if not self.credentials:
            return False

        self.session = requests.Session()

        # First register if we haven't already
        register_data = {
            "username": self.credentials["username"],
            "password": self.credentials["password"],
        }

        # Try registration (might fail if user exists, which is fine)
        response = self.session.post(
            f"{self.base_url}/api/register", json=register_data, timeout=self.timeout
        )

        # Now login
        login_data = {
            "username": self.credentials["username"],
            "password": self.credentials["password"],
        }

        response = self.session.post(
            f"{self.base_url}/api/login", json=login_data, timeout=self.timeout
        )
        return response.status_code == 200

    def test_health_endpoint(self):
        """Test /api/health endpoint"""
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
        """Test /api/me endpoint"""
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

    def test_list_vaults_endpoint(self):
        """Test GET /api/vaults endpoint"""
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
        """Test POST /api/vaults endpoint"""
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
                # Store vault_id for other tests
                self.credentials["test_vault_id"] = vault_id
                self.credentials["test_vault_name"] = vault_name

            return "vault_id" in data
        except Exception as e:
            logging.error(f"Create vault endpoint test failed: {e}")
            return False

    def test_get_vault_entries_endpoint(self):
        """Test GET /api/vaults/<id>/entries endpoint"""
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                # Create a vault first
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
        """Test POST /api/vaults/<id>/entries endpoint"""
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
        """Test /api/validate-entry endpoint"""
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
        """Test POST /api/vaults/<id>/import endpoint"""
        try:
            vault_id = self.credentials.get("test_vault_id")
            if not vault_id:
                # Create a vault first
                if not self.test_create_vault_endpoint():
                    return False
                vault_id = self.credentials.get("test_vault_id")

            # Create test CSV data
            csv_content = "https://csv.example.com,csvuser,csvpass123"

            # Prepare form data
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
        """Test POST /api/vaults/<id>/download endpoint"""
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

            # Should return binary data
            return response.status_code == 200 and len(response.content) > 0
        except Exception as e:
            logging.error(f"Download vault endpoint test failed: {e}")
            return False

    def test_delete_vault_endpoint(self):
        """Test DELETE /api/vaults/<id> endpoint"""
        try:
            # Create a vault specifically for deletion
            vault_name = f"delete_test_{self.generate_vault_name()}"
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

            # Now delete it
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

        # Setup credentials
        if not self.setup_credentials():
            return {"error": "Failed to setup credentials"}

        # Login
        if not self.login_with_credentials():
            return {"error": "Failed to login"}

        # Run all tests
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

        return results

    def cleanup(self):
        """Cleanup session"""
        if self.session:
            try:
                self.session.close()
            except:
                pass
