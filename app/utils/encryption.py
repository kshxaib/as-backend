import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv


load_dotenv()

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")


if not ENCRYPTION_KEY:
    raise RuntimeError(
        "ENCRYPTION_KEY is not configured in the environment."
    )

    
fernet = Fernet(ENCRYPTION_KEY.encode())


def encrypt_api_key(api_key: str) -> str:
    encrypted_key = fernet.encrypt(api_key.encode())
    return encrypted_key.decode()


def decrypt_api_key(encrypted_api_key: str) -> str:
    decrypted_key = fernet.decrypt(encrypted_api_key.encode())
    return decrypted_key.decode()