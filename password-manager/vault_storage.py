import os
import uuid
from pathlib import Path
from crypto_utils import VaultCrypto, CSVFormatter
from config import Config


class VaultStorage:
    """Handles vault file operations on disk"""

    def __init__(self, vaults_dir=None):
        self.vaults_dir = Path(vaults_dir or Config.VAULTS_DIR)
        self.vaults_dir.mkdir(exist_ok=True)

    def save_vault(self, entries, master_password, comment=None):
        """Save encrypted vault to disk, return filename"""
        # Format entries as CSV
        csv_content = CSVFormatter.format_vault(entries, comment)

        # Encrypt the CSV content
        encrypted_data = VaultCrypto.encrypt_data(csv_content, master_password)

        # Generate unique filename
        filename = f"{uuid.uuid4().hex}.vault"
        filepath = self.vaults_dir / filename

        # Write encrypted data to file
        with open(filepath, "wb") as f:
            f.write(encrypted_data)

        return filename

    def load_vault(self, filename, master_password):
        """Load and decrypt vault from disk"""
        filepath = self.vaults_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Vault file {filename} not found")

        # Read encrypted data
        with open(filepath, "rb") as f:
            encrypted_data = f.read()

        try:
            # Decrypt and parse
            csv_content = VaultCrypto.decrypt_data(encrypted_data, master_password)
            entries = CSVFormatter.parse_vault_csv(csv_content)
            return entries
        except Exception as e:
            raise ValueError(
                "Failed to decrypt vault - incorrect master password or corrupted data"
            )

    def vault_exists(self, filename):
        """Check if vault file exists"""
        filepath = self.vaults_dir / filename
        return filepath.exists()

    def delete_vault_file(self, filename):
        """Delete vault file from disk"""
        filepath = self.vaults_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_vault_for_download(self, filename, master_password, comment=None):
        """Get vault data for download (with optional comment)"""
        # Load existing vault
        entries = self.load_vault(filename, master_password)

        # Create new encrypted blob with comment
        csv_content = CSVFormatter.format_vault(entries, comment)
        encrypted_data = VaultCrypto.encrypt_data(csv_content, master_password)

        return encrypted_data


class VaultManager:
    """High-level vault management operations"""

    def __init__(self, database, storage=None):
        self.db = database
        self.storage = storage or VaultStorage()

    def create_vault(self, user_id, vault_name, entries, master_password):
        """Create a new vault with password entries"""
        # Validate all entries
        for entry in entries:
            valid, error = CSVFormatter.validate_entry(
                entry["url"], entry["username"], entry["password"]
            )
            if not valid:
                raise ValueError(f"Invalid entry: {error}")

        # Save encrypted vault to disk
        filename = self.storage.save_vault(entries, master_password)

        # Create database record
        vault_id = self.db.create_vault(user_id, vault_name, filename)
        if not vault_id:
            # Clean up file if database insert failed
            self.storage.delete_vault_file(filename)
            raise ValueError("Vault name already exists")

        return vault_id

    def get_vault_entries(self, vault_id, user_id, master_password):
        """Get decrypted entries from a vault"""
        # Get vault info from database
        vault = self.db.get_vault(vault_id, user_id)
        if not vault:
            raise ValueError("Vault not found or access denied")

        # Load and decrypt vault
        entries = self.storage.load_vault(vault["filename"], master_password)
        return entries

    def add_entries_to_vault(self, vault_id, user_id, new_entries, master_password):
        """Add new entries to existing vault"""
        # Get existing entries
        existing_entries = self.get_vault_entries(vault_id, user_id, master_password)

        # Validate new entries
        for entry in new_entries:
            valid, error = CSVFormatter.validate_entry(
                entry["url"], entry["username"], entry["password"]
            )
            if not valid:
                raise ValueError(f"Invalid entry: {error}")

        # Combine entries
        all_entries = existing_entries + new_entries

        # Get vault info
        vault = self.db.get_vault(vault_id, user_id)

        # Save updated vault
        new_filename = self.storage.save_vault(all_entries, master_password)

        # Update database with new filename
        old_filename = vault["filename"]
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE vaults SET filename = ? WHERE id = ? AND user_id = ?
            """,
                (new_filename, vault_id, user_id),
            )
            conn.commit()

        # Delete old file
        self.storage.delete_vault_file(old_filename)

        return len(new_entries)

    def delete_vault(self, vault_id, user_id):
        """Delete a vault completely"""
        # Get vault info
        vault = self.db.get_vault(vault_id, user_id)
        if not vault:
            return False

        # Delete from database
        success = self.db.delete_vault(vault_id, user_id)
        if success:
            # Delete file
            self.storage.delete_vault_file(vault["filename"])

        return success

    def download_vault(self, vault_id, master_password, comment=None):
        """Prepare vault for download with optional comment"""
        # Get vault info (allow any user to download any vault)
        vault = self.db.get_vault(vault_id)
        if not vault:
            raise ValueError("Vault not found")

        # Get encrypted data for download
        encrypted_data = self.storage.get_vault_for_download(
            vault["filename"], master_password, comment
        )

        return encrypted_data, f"{vault['name']}.vault"
