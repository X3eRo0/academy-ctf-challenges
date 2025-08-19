import os
import uuid
from pathlib import Path
from crypto_client import VaultCrypto, CSVFormatter
from config import Config


class VaultStorage:
    def __init__(self, vaults_dir=None):
        self.vaults_dir = Path(vaults_dir or Config.VAULTS_DIR)
        self.vaults_dir.mkdir(exist_ok=True)

    def save_vault(self, entries, master_password, comment=None):
        csv_content = CSVFormatter.format_vault(entries, comment)
        encrypted_data = VaultCrypto.encrypt_data(csv_content, master_password)
        filename = f"{uuid.uuid4().hex}.vault"
        filepath = self.vaults_dir / filename
        with open(filepath, "wb") as f:
            f.write(encrypted_data)

        return filename

    def load_vault(self, filename, master_password):
        filepath = self.vaults_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Vault file {filename} not found")
        with open(filepath, "rb") as f:
            encrypted_data = f.read()

        try:
            csv_content = VaultCrypto.decrypt_data(encrypted_data, master_password)
            entries = CSVFormatter.parse_vault_csv(csv_content)
            return entries
        except Exception as e:
            raise ValueError(
                "Failed to decrypt vault - incorrect master password or corrupted data"
            )

    def vault_exists(self, filename):
        filepath = self.vaults_dir / filename
        return filepath.exists()

    def delete_vault_file(self, filename):
        filepath = self.vaults_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_vault_for_download(self, filename, master_password, comment=None):
        entries = self.load_vault(filename, master_password)
        csv_content = CSVFormatter.format_vault(entries, comment)
        encrypted_data = VaultCrypto.encrypt_data(csv_content, master_password)

        return encrypted_data


class VaultManager:
    def __init__(self, database, storage=None):
        self.db = database
        self.storage = storage or VaultStorage()

    def create_vault(self, user_id, vault_name, entries, master_password):
        for entry in entries:
            valid, error = CSVFormatter.validate_entry(
                entry.get("url", entry.get("service", "")),
                entry["username"],
                entry["password"],
            )
            if not valid:
                raise ValueError(f"Invalid entry: {error}")
        filename = self.storage.save_vault(entries, master_password)
        vault_id = self.db.create_vault(user_id, vault_name, filename, master_password)
        if not vault_id:
            self.storage.delete_vault_file(filename)
            raise ValueError("Vault name already exists")

        return vault_id

    def get_vault_entries(self, vault_id, user_id, master_password):
        vault = self.db.get_vault(vault_id, user_id)
        if not vault:
            raise ValueError("Vault not found or access denied")
        entries = self.storage.load_vault(vault["filename"], master_password)
        return entries

    def add_entries_to_vault(self, vault_id, user_id, new_entries, master_password):
        existing_entries = self.get_vault_entries(vault_id, user_id, master_password)
        for entry in new_entries:
            valid, error = CSVFormatter.validate_entry(
                entry.get("url", entry.get("service", "")),
                entry["username"],
                entry["password"],
            )
            if not valid:
                raise ValueError(f"Invalid entry: {error}")
        all_entries = existing_entries + new_entries
        vault = self.db.get_vault(vault_id, user_id)
        new_filename = self.storage.save_vault(all_entries, master_password)
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
        self.storage.delete_vault_file(old_filename)

        return len(new_entries)

    def delete_vault(self, vault_id, user_id):
        vault = self.db.get_vault(vault_id, user_id)
        if not vault:
            return False
        success = self.db.delete_vault(vault_id, user_id)
        if success:
            self.storage.delete_vault_file(vault["filename"])

        return success

    def download_vault(self, vault_id, comment=None):
        vault = self.db.get_vault(vault_id)
        if not vault:
            raise ValueError("Vault not found")
        master_password = vault["master_password"]
        encrypted_data = self.storage.get_vault_for_download(
            vault["filename"], master_password, comment
        )

        return encrypted_data, f"{vault['name']}.vault"
