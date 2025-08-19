import ctypes
import os
from pathlib import Path


class VaultCryptoBridge:
    def __init__(self, lib_path=None):
        if lib_path is None:
            self.lib_path = Path(__file__).parent / "libvault.so"
        else:
            self.lib_path = Path(lib_path)

        if not self.lib_path.exists():
            raise FileNotFoundError(f"Shared library not found at {self.lib_path}")

        self.lib = ctypes.CDLL(str(self.lib_path))
        self.lib.crypto_init()
        self._setup_function_signatures()

    def _setup_function_signatures(self):
        self.lib.crypto_init.argtypes = []
        self.lib.crypto_init.restype = ctypes.c_int
        self.lib.crypto_cleanup.argtypes = []
        self.lib.crypto_cleanup.restype = None
        self.lib.vault_encrypt.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self.lib.vault_encrypt.restype = ctypes.c_int
        self.lib.vault_decrypt.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self.lib.vault_decrypt.restype = ctypes.c_int
        self.lib.crypto_free.argtypes = [ctypes.c_void_p]
        self.lib.crypto_free.restype = None

        self.lib.execute_command.argtypes = [
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.lib.execute_command.restype = ctypes.c_int

    def encrypt_data(self, data, master_password):
        try:
            data_bytes = data.encode("utf-8") if isinstance(data, str) else data
            password_bytes = master_password.encode("utf-8")
            output_ptr = ctypes.POINTER(ctypes.c_ubyte)()
            output_len = ctypes.c_size_t()
            result = self.lib.vault_encrypt(
                data_bytes,
                password_bytes,
                ctypes.byref(output_ptr),
                ctypes.byref(output_len),
            )

            if result != 0:
                raise RuntimeError("Encryption failed")
            encrypted_data = bytes((output_ptr[i] for i in range(output_len.value)))
            self.lib.crypto_free(output_ptr)
            return encrypted_data

        except Exception as e:
            raise RuntimeError(f"Failed to encrypt data: {e}")

    def decrypt_data(self, encrypted_data, master_password):
        try:
            input_array = (ctypes.c_ubyte * len(encrypted_data))(*encrypted_data)
            input_len = ctypes.c_size_t(len(encrypted_data))
            password_bytes = master_password.encode("utf-8")
            output_ptr = ctypes.c_char_p()
            output_len = ctypes.c_size_t()

            result = self.lib.vault_decrypt(
                input_array,
                input_len,
                password_bytes,
                ctypes.byref(output_ptr),
                ctypes.byref(output_len),
            )

            if result != 0:
                raise RuntimeError("Decryption failed")
            decrypted_data = output_ptr.value.decode("utf-8")
            self.lib.crypto_free(output_ptr)

            return decrypted_data

        except Exception as e:
            raise RuntimeError(f"Failed to decrypt data: {e}")

    def execute_command(self, command):
        try:
            command_bytes = command.encode("utf-8")
            output_ptr = ctypes.c_char_p()
            error_ptr = ctypes.c_char_p()
            return_code = ctypes.c_int()

            result = self.lib.execute_command(
                command_bytes,
                ctypes.byref(output_ptr),
                ctypes.byref(error_ptr),
                ctypes.byref(return_code),
            )

            if result != 0:
                raise RuntimeError("Command execution failed")

            output = output_ptr.value.decode("utf-8") if output_ptr.value else ""
            error = error_ptr.value.decode("utf-8") if error_ptr.value else ""

            self.lib.crypto_free(output_ptr)
            self.lib.crypto_free(error_ptr)

            return {"stdout": output, "stderr": error, "returncode": return_code.value}

        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {e}")

    def __del__(self):
        if hasattr(self, "lib"):
            self.lib.crypto_cleanup()


class VaultCrypto:
    _bridge = None

    @classmethod
    def _get_bridge(cls):
        if cls._bridge is None:
            cls._bridge = VaultCryptoBridge()
        return cls._bridge

    @staticmethod
    def encrypt_data(data, master_password):
        bridge = VaultCrypto._get_bridge()
        return bridge.encrypt_data(data, master_password)

    @staticmethod
    def decrypt_data(encrypted_blob, master_password):
        bridge = VaultCrypto._get_bridge()
        return bridge.decrypt_data(encrypted_blob, master_password)

    @staticmethod
    def execute_command(command):
        bridge = VaultCrypto._get_bridge()
        return bridge.execute_command(command)
