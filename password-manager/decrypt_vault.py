#!/usr/bin/env python3
"""
Vault Decryption Script
Decrypt password manager vault files with master password
"""

import sys
import argparse
from pathlib import Path
from crypto_utils import VaultCrypto, CSVFormatter

def decrypt_vault_file(vault_path, master_password, output_format='csv'):
    """
    Decrypt a vault file and return the contents
    
    Args:
        vault_path: Path to the encrypted .vault file
        master_password: Master password for decryption
        output_format: 'csv' or 'json' output format
    
    Returns:
        Decrypted vault contents
    """
    vault_file = Path(vault_path)
    
    if not vault_file.exists():
        raise FileNotFoundError(f"Vault file not found: {vault_path}")
    
    # Read encrypted data from file
    with open(vault_file, 'rb') as f:
        encrypted_data = f.read()
    
    print(f"DEBUG: Read {len(encrypted_data)} bytes from vault file", file=sys.stderr)
    print(f"DEBUG: First 32 bytes (hex): {encrypted_data[:32].hex()}", file=sys.stderr)
    
    # Check minimum size (salt=16 + iv=16 + at least some encrypted data)
    if len(encrypted_data) < 32:
        raise ValueError(f"Vault file too small ({len(encrypted_data)} bytes) - corrupted or invalid")
    
    try:
        # Extract components for debugging
        salt = encrypted_data[:16]
        iv = encrypted_data[16:32]
        encrypted_content = encrypted_data[32:]
        print(f"DEBUG: Salt: {salt.hex()}", file=sys.stderr)
        print(f"DEBUG: IV: {iv.hex()}", file=sys.stderr)
        print(f"DEBUG: Encrypted content: {len(encrypted_content)} bytes", file=sys.stderr)
        
        # Decrypt the vault data
        csv_content = VaultCrypto.decrypt_data(encrypted_data, master_password)
        print(f"DEBUG: Decrypted CSV content ({len(csv_content)} chars):\n{repr(csv_content)}", file=sys.stderr)
        print(f"DEBUG: Raw CSV content as seen:\n{csv_content}", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        
        # Parse entries from CSV
        entries = CSVFormatter.parse_vault_csv(csv_content)
        print(f"DEBUG: Parsed {len(entries)} entries", file=sys.stderr)
        
        if output_format == 'csv':
            # Create clean CSV without quotes and with trimmed whitespace
            # But preserve comments from original CSV
            clean_lines = []
            original_lines = csv_content.strip().split('\n')
            
            entry_index = 0
            for line in original_lines:
                line = line.strip()
                if line.startswith('#'):
                    # Preserve comments as-is
                    clean_lines.append(line)
                elif line and not line.startswith('"URL"'):  # Skip header if present
                    # Process data lines
                    if entry_index < len(entries):
                        entry = entries[entry_index]
                        url = entry['url'].strip()
                        username = entry['username'].strip() 
                        password = entry['password'].strip()
                        clean_lines.append(f"{url},{username},{password}")
                        entry_index += 1
            
            return '\n'.join(clean_lines)
        elif output_format == 'json':
            import json
            # Clean entries for JSON output too
            clean_entries = []
            for entry in entries:
                clean_entries.append({
                    'url': entry['url'].strip(),
                    'username': entry['username'].strip(),
                    'password': entry['password'].strip()
                })
            return json.dumps(clean_entries, indent=2)
        else:
            # Clean entries for raw output
            clean_entries = []
            for entry in entries:
                clean_entries.append({
                    'url': entry['url'].strip(),
                    'username': entry['username'].strip(),
                    'password': entry['password'].strip()
                })
            return clean_entries
            
    except Exception as e:
        print(f"DEBUG: Exception during decryption: {e}", file=sys.stderr)
        raise ValueError(f"Failed to decrypt vault - incorrect master password or corrupted data: {e}")

def main():
    parser = argparse.ArgumentParser(description='Decrypt password manager vault files')
    parser.add_argument('vault_file', help='Path to the encrypted .vault file')
    parser.add_argument('master_password', help='Master password for decryption')
    parser.add_argument('-f', '--format', choices=['csv', 'json', 'entries'], 
                       default='csv', help='Output format (default: csv)')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    
    args = parser.parse_args()
    
    try:
        # Decrypt the vault
        result = decrypt_vault_file(args.vault_file, args.master_password, args.format)
        
        # Output result
        if args.output:
            with open(args.output, 'w') as f:
                if args.format in ['csv', 'json']:
                    f.write(result)
                else:
                    # entries format - pretty print
                    for i, entry in enumerate(result, 1):
                        f.write(f"Entry {i}:\n")
                        f.write(f"  URL: {entry['url']}\n")
                        f.write(f"  Username: {entry['username']}\n")
                        f.write(f"  Password: {entry['password']}\n\n")
            print(f"Decrypted vault saved to: {args.output}")
        else:
            if args.format in ['csv', 'json']:
                print(result)
            else:
                # entries format - pretty print to stdout
                for i, entry in enumerate(result, 1):
                    print(f"Entry {i}:")
                    print(f"  URL: {entry['url']}")
                    print(f"  Username: {entry['username']}")  
                    print(f"  Password: {entry['password']}")
                    print()
                    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()