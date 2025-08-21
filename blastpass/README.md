# BlastPass - Secure Password Vault Service

BlastPass is a secure password vault service that allows users to store, manage, and share encrypted password vaults with advanced cryptographic protection.

## Quick Start with Docker

1. Start the BlastPass service:
```bash
./run.sh start
```

2. Stop the service:
```bash
./run.sh stop
```

## Available Commands

- `./run.sh start` - Start the BlastPass service
- `./run.sh stop` - Stop all services
- `./run.sh logs` - Show service logs
- `./run.sh clean` - Clean up containers and volumes
- `./run.sh shell` - Open shell in container

The service runs on `http://localhost:3333` when started with Docker.

## Features

- **Secure User Authentication** - Register and login with master passwords
- **Encrypted Vault Storage** - AES-256 encryption with zlib compression
- **CSV Import/Export** - Import password data from CSV files or URLs
- **Vault Sharing** - Download and share encrypted vault files
- **Web Interface** - Complete web UI for vault management
- **REST API** - Full API access for programmatic integration

## API Endpoints

### Authentication
- `POST /api/register` - Register new user account
- `POST /api/login` - User authentication
- `POST /api/logout` - End user session
- `GET /api/me` - Get current user information

### Vault Management
- `GET /api/vaults` - List user's vaults
- `POST /api/vaults` - Create new encrypted vault
- `GET /api/vaults/{id}/entries` - Decrypt and view vault entries
- `POST /api/vaults/{id}/entries` - Add entries to existing vault
- `DELETE /api/vaults/{id}` - Delete vault
- `POST /api/vaults/{id}/import` - Import CSV data to vault
- `POST /api/vaults/{id}/download` - Download encrypted vault file

### Utility
- `POST /api/validate-entry` - Validate password entry format
- `GET /api/health` - Service health check

## Security Architecture

- **PBKDF2 Password Hashing** - Master passwords use strong key derivation
- **AES-256 Encryption** - Vault data encrypted with user's master password
- **Zlib Compression** - Data compressed before encryption for efficiency
- **File-based Storage** - Encrypted vaults stored as individual files
- **Public Vault Access** - Anyone can download vault files, but decryption requires master password
