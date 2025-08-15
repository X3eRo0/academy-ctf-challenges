import os
import gzip
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


class VaultCrypto:
    """Handles encryption, decryption, and compression for password vaults"""

    @staticmethod
    def derive_key(master_password, salt):
        """Derive encryption key from master password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key for AES-256
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(master_password.encode("utf-8"))

    @staticmethod
    def compress_data(data):
        """Compress data using gzip"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return gzip.compress(data)

    @staticmethod
    def decompress_data(compressed_data):
        """Decompress gzip data"""
        return gzip.decompress(compressed_data).decode("utf-8")

    @staticmethod
    def encrypt_data(data, master_password):
        """Compress and encrypt data with master password"""
        # Compress first
        compressed_data = VaultCrypto.compress_data(data)

        # Generate random salt and IV
        salt = os.urandom(16)
        iv = os.urandom(16)

        # Derive key from master password
        key = VaultCrypto.derive_key(master_password, salt)

        # Encrypt using AES-256-CBC
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Pad data to AES block size (16 bytes)
        padded_data = VaultCrypto._pad_data(compressed_data)
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        # Return salt + iv + encrypted_data
        return salt + iv + encrypted_data

    @staticmethod
    def decrypt_data(encrypted_blob, master_password):
        """Decrypt and decompress data with master password"""
        # Extract components
        salt = encrypted_blob[:16]
        iv = encrypted_blob[16:32]
        encrypted_data = encrypted_blob[32:]

        # Derive key from master password
        key = VaultCrypto.derive_key(master_password, salt)

        # Decrypt using AES-256-CBC
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # Remove padding
        compressed_data = VaultCrypto._unpad_data(padded_data)

        # Decompress
        return VaultCrypto.decompress_data(compressed_data)

    @staticmethod
    def _pad_data(data):
        """PKCS7 padding for AES"""
        pad_length = 16 - (len(data) % 16)
        padding = bytes([pad_length] * pad_length)
        return data + padding

    @staticmethod
    def _unpad_data(padded_data):
        """Remove PKCS7 padding"""
        pad_length = padded_data[-1]
        return padded_data[:-pad_length]


class CSVFormatter:
    """Handles CSV formatting and parsing for password entries"""

    @staticmethod
    def format_entry(url, username, password):
        """Format a single password entry as CSV line"""
        # Don't quote fields - just use comma separation
        return f"{url},{username},{password}"

    @staticmethod
    def format_vault(entries, comment=None):
        """Format multiple entries into a CSV vault"""
        lines = []

        # Add comment at the top if provided
        if comment:
            lines.append(f"# {comment}")

        # Add entries
        for entry in entries:
            lines.append(
                CSVFormatter.format_entry(
                    entry["url"], entry["username"], entry["password"]
                )
            )

        result = "\n".join(lines)
        return result

    @staticmethod
    def parse_csv_line(line):
        """Parse a single CSV line into url, username, password"""
        import csv
        import io

        # Skip comments and empty lines
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        # Parse CSV line
        reader = csv.reader(io.StringIO(line))
        try:
            fields = next(reader)
            if len(fields) != 3:
                return None

            # No URL decoding needed - use fields as-is but strip whitespace
            url = fields[0].strip()
            username = fields[1].strip()
            password = fields[2].strip()

            return {"url": url, "username": username, "password": password}
        except:
            return None

    @staticmethod
    def parse_vault_csv(csv_content):
        """Parse entire CSV vault into list of entries"""
        entries = []
        lines = csv_content.strip().split("\n")

        for i, line in enumerate(lines):
            entry = CSVFormatter.parse_csv_line(line)
            if entry:
                entries.append(entry)

        return entries

    @staticmethod
    def validate_entry(url, username, password):
        """Validate a password entry according to rules"""
        # Check if username and password don't contain commas
        import re

        if not url or not username or not password:
            return False, "All fields are required"

        # Username and password: no commas allowed (interferes with CSV format)
        if "," in username:
            return False, "Username cannot contain commas (interferes with CSV format)"

        if "," in password:
            return False, "Password cannot contain commas (interferes with CSV format)"

        return True, ""
