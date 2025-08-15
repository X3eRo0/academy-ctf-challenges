# Password Manager CTF Challenge - Backend

A simple password manager service for CTF challenges.

## Quick Start with Docker

1. Start the service:
```bash
./run.sh start
```

2. Run tests:
```bash
./run.sh test
```

3. Stop the service:
```bash
./run.sh stop
```

## Available Commands

- `./run.sh start` - Start the password manager service
- `./run.sh test` - Run the test suite  
- `./run.sh stop` - Stop all services
- `./run.sh logs` - Show service logs
- `./run.sh clean` - Clean up containers and volumes
- `./run.sh shell` - Open shell in container

## Manual Setup (without Docker)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask application:
```bash
python app.py
```

The server will start on `http://localhost:5000`

## Testing

Run the test script to verify functionality:
```bash
python test_backend.py
```

## API Endpoints

### Authentication
- `POST /api/register` - Register new user
- `POST /api/login` - User login  
- `POST /api/logout` - User logout
- `GET /api/me` - Get current user info

### Vaults
- `GET /api/vaults` - Get user's vaults
- `POST /api/vaults` - Create new vault
- `GET /api/vaults/{id}/entries` - Get vault entries (requires master password)
- `POST /api/vaults/{id}/entries` - Add entries to vault
- `DELETE /api/vaults/{id}` - Delete vault
- `POST /api/vaults/{id}/import` - Import CSV file
- `POST /api/vaults/{id}/download` - Download vault (anyone can download any vault)

### Utility
- `POST /api/validate-entry` - Validate password entry
- `GET /api/health` - Health check

## Features

- User registration with master password
- Encrypted vault storage (AES-256 + compression)
- CSV import/export functionality
- Vault sharing through download (with optional comments)
- ASCII-only username/password validation
- Session-based authentication

## Security Model

- Master passwords are hashed with PBKDF2
- Vault data is compressed then encrypted with master password
- Each vault is stored as encrypted file on disk
- Anyone can download any vault but needs master password to decrypt
