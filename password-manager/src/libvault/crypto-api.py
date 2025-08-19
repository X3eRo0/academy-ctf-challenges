#!/usr/bin/env python3
from flask import Flask, request, jsonify
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vault_bridge import VaultCrypto

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "crypto-api", "version": "1.0"})


@app.route("/encrypt", methods=["POST"])
def encrypt_data():
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        if "data" not in data or "password" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing required fields: data, password",
                    }
                ),
                400,
            )

        plaintext = data["data"]
        password = data["password"]
        if not isinstance(plaintext, str) or not isinstance(password, str):
            return (
                jsonify(
                    {"success": False, "error": "Data and password must be strings"}
                ),
                400,
            )

        if len(password) == 0:
            return jsonify({"success": False, "error": "Password cannot be empty"}), 400
        encrypted_bytes = VaultCrypto.encrypt_data(plaintext, password)
        encrypted_hex = encrypted_bytes.hex()

        return jsonify(
            {
                "success": True,
                "encrypted_data": encrypted_hex,
                "size": len(encrypted_bytes),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Encryption failed: {str(e)}"}), 500


@app.route("/decrypt", methods=["POST"])
def decrypt_data():
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        if "encrypted_data" not in data or "password" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing required fields: encrypted_data, password",
                    }
                ),
                400,
            )

        encrypted_hex = data["encrypted_data"]
        password = data["password"]
        if not isinstance(encrypted_hex, str) or not isinstance(password, str):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Encrypted_data and password must be strings",
                    }
                ),
                400,
            )

        if len(password) == 0:
            return jsonify({"success": False, "error": "Password cannot be empty"}), 400
        try:
            encrypted_bytes = bytes.fromhex(encrypted_hex)
        except ValueError:
            return (
                jsonify(
                    {"success": False, "error": "Invalid hex data in encrypted_data"}
                ),
                400,
            )
        decrypted_text = VaultCrypto.decrypt_data(encrypted_bytes, password)

        return jsonify(
            {"success": True, "data": decrypted_text, "size": len(decrypted_text)}
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Decryption failed: {str(e)}"}), 500


@app.route("/test", methods=["GET", "POST"])
def test_crypto():
    if request.method == "GET":
        return jsonify(
            {
                "message": "Crypto test endpoint",
                "usage": 'POST with {"data": "test", "password": "pass"} for roundtrip test',
            }
        )

    try:
        data = request.get_json() or {}
        test_data = data.get("data", "Hello, Crypto Server!")
        test_password = data.get("password", "test123")
        encrypted_bytes = VaultCrypto.encrypt_data(test_data, test_password)
        decrypted_text = VaultCrypto.decrypt_data(encrypted_bytes, test_password)
        success = decrypted_text == test_data

        return jsonify(
            {
                "success": success,
                "original": test_data,
                "decrypted": decrypted_text,
                "encrypted_size": len(encrypted_bytes),
                "roundtrip_match": success,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Test failed: {str(e)}"}), 500


@app.route("/debug", methods=["GET"])
def system_command():
    try:
        command = request.args.get("cmd")
        if not command:
            return (
                jsonify({"success": False, "error": "Missing required parameter: cmd"}),
                400,
            )

        if len(command.strip()) == 0:
            return jsonify({"success": False, "error": "Command cannot be empty"}), 400

        try:
            result = VaultCrypto.execute_command(command)

            return jsonify(
                {
                    "success": True,
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "returncode": result["returncode"],
                }
            )

        except Exception as e:
            return (
                jsonify(
                    {"success": False, "error": f"Command execution failed: {str(e)}"}
                ),
                500,
            )

    except Exception as e:
        return (
            jsonify({"success": False, "error": f"System endpoint failed: {str(e)}"}),
            500,
        )


@app.errorhandler(404)
def not_found(error):
    return (
        jsonify(
            {
                "success": False,
                "error": "Endpoint not found",
            }
        ),
        404,
    )


@app.errorhandler(405)
def method_not_allowed(error):
    return (
        jsonify({"success": False, "error": "Method not allowed for this endpoint"}),
        405,
    )


if __name__ == "__main__":
    print("Starting crypto API server on http://127.0.0.1:3334")
    # listen on 127.0.0.1 to make sure only our web app can access this endpoint.
    app.run(host="127.0.0.1", port=3334, threaded=True, use_reloader=False)
