# security.py
import hashlib
import base64
import secrets
import logging

class PasswordManager:
    @staticmethod
    def hash_password(password: str) -> str:
        """Genera un hash seguro de la contraseña usando SHA-256"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        # Formato: hash:salt
        return f"{password_hash}:{salt}"
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verifica si la contraseña coincide con el hash almacenado"""
        try:
            # if ':' not in hashed_password:
            #     # Si no tiene formato hash:salt, asume contraseña sin encriptar (para migración)
            #     return password == hashed_password
                
            stored_hash, salt = hashed_password.split(":")
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return password_hash == stored_hash
        except Exception as e:
            logging.error(f"Error verificando contraseña: {e}")
            return False