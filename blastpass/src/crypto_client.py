"""HTTP client for crypto frontend service"""

import requests
import json
from typing import Tuple, List, Dict, Optional


class VaultCrypto:
    """HTTP client wrapper for crypto operations"""

    FRONTEND_URL = "http://127.0.0.1:3334"

    @staticmethod
    def encrypt_data(data: str, master_password: str) -> bytes:
        """Encrypt data using the frontend service"""
        try:
            payload = {"data": data, "password": master_password}

            response = requests.post(
                f"{VaultCrypto.FRONTEND_URL}/encrypt",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = "Unknown error"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", "Unknown error")
                except:
                    error_msg = f"HTTP {response.status_code}"
                raise RuntimeError(f"Encryption failed: {error_msg}")

            result = response.json()
            if not result.get("success"):
                raise RuntimeError(
                    f"Encryption failed: {result.get('error', 'Unknown error')}"
                )

            # Convert hex string back to bytes
            encrypted_hex = result.get("encrypted_data")
            if not encrypted_hex:
                raise RuntimeError("No encrypted data in response")

            return bytes.fromhex(encrypted_hex)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to connect to crypto frontend: {e}")
        except Exception as e:
            raise RuntimeError(f"Encryption failed: {e}")

    @staticmethod
    def decrypt_data(encrypted_data: bytes, master_password: str) -> str:
        """Decrypt data using the frontend service"""
        try:
            payload = {
                "encrypted_data": encrypted_data.hex(),
                "password": master_password,
            }

            response = requests.post(
                f"{VaultCrypto.FRONTEND_URL}/decrypt",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = "Unknown error"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", "Unknown error")
                except:
                    error_msg = f"HTTP {response.status_code}"
                raise RuntimeError(f"Decryption failed: {error_msg}")

            result = response.json()
            if not result.get("success"):
                raise RuntimeError(
                    f"Decryption failed: {result.get('error', 'Unknown error')}"
                )

            decrypted_data = result.get("data")
            if decrypted_data is None:
                raise RuntimeError("No decrypted data in response")

            return decrypted_data

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to connect to crypto frontend: {e}")
        except Exception as e:
            raise RuntimeError(f"Decryption failed: {e}")


class CSVFormatter:
    """CSV formatting utilities (moved from crypto_bridge)"""

    @staticmethod
    def format_vault(entries: List[Dict], comment: Optional[str] = None) -> str:
        """Format entries as CSV with optional comment"""
        csv_lines = []

        # Add comment if provided
        if comment:
            csv_lines.append(f"# {comment}")

        # # Add CSV header
        # csv_lines.append("URL,Username,Password")

        # Add entries
        for entry in entries:
            url = entry.get("url", entry.get("service", "")).replace(",", "\\,")
            username = entry.get("username", "").replace(",", "\\,")
            password = entry.get("password", "").replace(",", "\\,")
            csv_lines.append(f"{url},{username},{password}")

        return "\n".join(csv_lines)

    @staticmethod
    def parse_vault(csv_content: str) -> Tuple[List[Dict], Optional[str]]:
        lines = csv_content.strip().split("\n")
        entries = []
        comment = None

        for line in lines:
            line = line.strip()
            if line.startswith("#"):
                comment = line[1:].strip()
            elif line:
                parts = line.split(",")
                if len(parts) >= 3:
                    entries.append(
                        {
                            "url": parts[0].replace("\\,", ","),
                            "username": parts[1].replace("\\,", ","),
                            "password": parts[2].replace("\\,", ","),
                        }
                    )

        return entries, comment

    @staticmethod
    def parse_vault_csv(csv_content: str) -> List[Dict]:
        """Parse CSV content to entries (alias for compatibility)"""
        entries, _ = CSVFormatter.parse_vault(csv_content)
        return entries

    @staticmethod
    def validate_entry(service: str, username: str, password: str) -> Tuple[bool, str]:
        """Validate a single entry"""
        if not service or not service.strip():
            return False, "Service cannot be empty"
        if not username or not username.strip():
            return False, "Username cannot be empty"
        if not password or not password.strip():
            return False, "Password cannot be empty"
        if len(service) > 200:
            return False, "Service name too long"
        if len(username) > 100:
            return False, "Username too long"
        if len(password) > 100:
            return False, "Password too long"
        return True, ""


__all__ = ["VaultCrypto", "CSVFormatter"]
