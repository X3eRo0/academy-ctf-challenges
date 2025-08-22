#!/usr/bin/env python3

import requests
import random
import string
import logging
from bs4 import BeautifulSoup
import tempfile
import io


class WebTestSuite:
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
        username = f"web_test_{self.generate_random_string(8)}"
        password = self.generate_random_password()
        master_password = self.generate_random_password()

        self.credentials = {
            "username": username,
            "password": password,
            "master_password": master_password,
        }

        return True

    def extract_csrf_token(self, response_text):
        soup = BeautifulSoup(response_text, "html.parser")
        csrf_input = soup.find("input", {"name": "csrf_token"})
        if csrf_input:
            return csrf_input.get("value")
        return None

    def test_home_page(self):
        try:
            response = self.session.get(f"{self.base_url}/", timeout=self.timeout)
            if response.status_code != 200:
                return False

            return "BlastPass" in response.text or "Password Manager" in response.text
        except Exception as e:
            logging.error(f"Home page test failed: {e}")
            return False

    def test_registration_page(self):
        try:
            response = self.session.get(
                f"{self.base_url}/register", timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            if "Register" not in response.text:
                return False

            form_data = {
                "username": self.credentials["username"],
                "password": self.credentials["password"],
                "confirm_password": self.credentials["password"],
            }

            csrf_token = self.extract_csrf_token(response.text)
            if csrf_token:
                form_data["csrf_token"] = csrf_token

            response = self.session.post(
                f"{self.base_url}/register", data=form_data, timeout=self.timeout
            )
            return response.status_code == 200 and (
                "dashboard" in response.url.lower()
                or "login" in response.url.lower()
                or "Welcome" in response.text
                or "successful" in response.text.lower()
            )
        except Exception as e:
            logging.error(f"Registration page test failed: {e}")
            return False

    def test_login_page(self):
        """Test user login through web interface"""
        try:
            response = self.session.get(f"{self.base_url}/login", timeout=self.timeout)
            if response.status_code != 200:
                return False

            if "Login" not in response.text:
                return False

            form_data = {
                "username": self.credentials["username"],
                "password": self.credentials["password"],
            }

            csrf_token = self.extract_csrf_token(response.text)
            if csrf_token:
                form_data["csrf_token"] = csrf_token

            response = self.session.post(
                f"{self.base_url}/login", data=form_data, timeout=self.timeout
            )
            return response.status_code == 200 and (
                "dashboard" in response.url.lower() or "Welcome" in response.text
            )
        except Exception as e:
            logging.error(f"Login page test failed: {e}")
            return False

    def test_dashboard_page(self):
        """Test the dashboard page loads and shows user content"""
        try:
            response = self.session.get(
                f"{self.base_url}/dashboard", timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            return (
                "dashboard" in response.text.lower()
                or "vault" in response.text.lower()
                or self.credentials["username"] in response.text
            )
        except Exception as e:
            logging.error(f"Dashboard page test failed: {e}")
            return False

    def test_create_vault_page(self):
        try:
            response = self.session.get(
                f"{self.base_url}/create-vault", timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            vault_name = self.generate_vault_name()
            form_data = {
                "vault_name": vault_name,
                "master_password": self.credentials["master_password"],
                "url_1": "https://example.com",
                "username_1": "testuser",
                "password_1": "testpass123",
            }
            csrf_token = self.extract_csrf_token(response.text)
            if csrf_token:
                form_data["csrf_token"] = csrf_token

            response = self.session.post(
                f"{self.base_url}/create-vault", data=form_data, timeout=self.timeout
            )
            self.credentials["test_vault_name"] = vault_name
            return response.status_code == 200 and (
                "success" in response.text.lower() or vault_name in response.text
            )
        except Exception as e:
            logging.error(f"Create vault page test failed: {e}")
            return False

    def test_vault_view_page(self):
        try:
            response = self.session.get(
                f"{self.base_url}/dashboard", timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            soup = BeautifulSoup(response.text, "html.parser")
            vault_links = soup.find_all("a", href=lambda x: x and "/vault/" in x)

            if not vault_links:
                if not self.test_create_vault_page():
                    return False
                response = self.session.get(
                    f"{self.base_url}/dashboard", timeout=self.timeout
                )
                soup = BeautifulSoup(response.text, "html.parser")
                vault_links = soup.find_all("a", href=lambda x: x and "/vault/" in x)

            if not vault_links:
                return False

            vault_url = vault_links[0]["href"]
            if not vault_url.startswith("http"):
                vault_url = f"{self.base_url}{vault_url}"

            response = self.session.get(vault_url, timeout=self.timeout)
            return response.status_code == 200 and "vault" in response.text.lower()
        except Exception as e:
            logging.error(f"Vault view page test failed: {e}")
            return False

    def test_vault_unlock(self):
        try:
            response = self.session.get(
                f"{self.base_url}/dashboard", timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            soup = BeautifulSoup(response.text, "html.parser")
            vault_links = soup.find_all("a", href=lambda x: x and "/vault/" in x)

            if not vault_links:
                if not self.test_create_vault_page():
                    return False
                response = self.session.get(
                    f"{self.base_url}/dashboard", timeout=self.timeout
                )
                soup = BeautifulSoup(response.text, "html.parser")
                vault_links = soup.find_all("a", href=lambda x: x and "/vault/" in x)

            if not vault_links:
                return False

            vault_url = vault_links[0]["href"]
            if not vault_url.startswith("http"):
                vault_url = f"{self.base_url}{vault_url}"

            form_data = {"master_password": self.credentials["master_password"]}

            response = self.session.post(
                vault_url, data=form_data, timeout=self.timeout
            )
            return response.status_code == 200 and (
                "example.com" in response.text or "entries" in response.text.lower()
            )
        except Exception as e:
            logging.error(f"Vault unlock test failed: {e}")
            return False

    def test_add_entries_page(self):
        """Test adding entries to a vault through web interface"""
        try:
            response = self.session.get(
                f"{self.base_url}/dashboard", timeout=self.timeout
            )
            soup = BeautifulSoup(response.text, "html.parser")
            vault_links = soup.find_all("a", href=lambda x: x and "/vault/" in x)

            if not vault_links:
                if not self.test_create_vault_page():
                    return False
                response = self.session.get(
                    f"{self.base_url}/dashboard", timeout=self.timeout
                )
                soup = BeautifulSoup(response.text, "html.parser")
                vault_links = soup.find_all("a", href=lambda x: x and "/vault/" in x)

            if not vault_links:
                return False

            vault_href = vault_links[0]["href"]
            vault_id = vault_href.split("/")[-1]

            add_url = f"{self.base_url}/vault/{vault_id}/add"
            response = self.session.get(add_url, timeout=self.timeout)
            if response.status_code != 200:
                return False

            form_data = {
                "master_password": self.credentials["master_password"],
                "url_1": "https://newsite.com",
                "username_1": "newuser",
                "password_1": "newpass456",
            }

            response = self.session.post(add_url, data=form_data, timeout=self.timeout)

            return response.status_code == 200 and (
                "success" in response.text.lower() or "added" in response.text.lower()
            )
        except Exception as e:
            logging.error(f"Add entries page test failed: {e}")
            return False

    def test_csv_import_page(self):
        try:
            response = self.session.get(
                f"{self.base_url}/import-csv", timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            csv_content = "https://csvtest.com,csvuser,csvpass123"
            csv_file = io.StringIO(csv_content)
            vault_name = f"csv_import_{self.generate_vault_name()}"

            files = {"file": ("test.csv", csv_content, "text/csv")}

            form_data = {
                "vault_name": vault_name,
                "master_password": self.credentials["master_password"],
                "import_method": "file",
            }

            response = self.session.post(
                f"{self.base_url}/import-csv",
                files=files,
                data=form_data,
                timeout=self.timeout,
            )
            return response.status_code == 200 and (
                "success" in response.text.lower() or vault_name in response.text
            )
        except Exception as e:
            logging.error(f"CSV import page test failed: {e}")
            return False

    def test_browse_vaults_page(self):
        try:
            response = self.session.get(
                f"{self.base_url}/browse-vaults", timeout=self.timeout
            )
            if response.status_code != 200:
                return False
            return "browse" in response.text.lower() or "vault" in response.text.lower()
        except Exception as e:
            logging.error(f"Browse vaults page test failed: {e}")
            return False

    def test_logout_functionality(self):
        try:
            response = self.session.get(f"{self.base_url}/logout", timeout=self.timeout)
            return response.status_code == 200 and (
                "login" in response.url.lower()
                or "home" in response.url.lower()
                or "login" in response.text.lower()
            )
        except Exception as e:
            logging.error(f"Logout functionality test failed: {e}")
            return False

    def run_all_web_tests(self):
        results = {}
        if not self.setup_credentials():
            return {"error": "Failed to setup credentials"}

        self.session = requests.Session()
        tests = [
            ("home_page", self.test_home_page),
            ("registration_page", self.test_registration_page),
            ("login_page", self.test_login_page),
            ("dashboard_page", self.test_dashboard_page),
            ("create_vault_page", self.test_create_vault_page),
            ("vault_view_page", self.test_vault_view_page),
            ("vault_unlock", self.test_vault_unlock),
            ("add_entries_page", self.test_add_entries_page),
            ("csv_import_page", self.test_csv_import_page),
            ("browse_vaults_page", self.test_browse_vaults_page),
            ("logout_functionality", self.test_logout_functionality),
        ]

        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
                logging.info(
                    f"Web test {test_name}: {'PASS' if results[test_name] else 'FAIL'}"
                )
            except Exception as e:
                results[test_name] = False
                logging.error(f"Web test {test_name} exception: {e}")

        return results

    def cleanup(self):
        if self.session:
            try:
                self.session.close()
            except:
                pass
