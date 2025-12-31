from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

@dataclass
class Ed25519Keypair:
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    def sign(self, msg: bytes) -> bytes:
        return self.private_key.sign(msg)

    def verify(self, sig: bytes, msg: bytes) -> None:
        self.public_key.verify(sig, msg)

def generate_keypair() -> Ed25519Keypair:
    priv = Ed25519PrivateKey.generate()
    return Ed25519Keypair(private_key=priv, public_key=priv.public_key())

def save_keypair(keypair: Ed25519Keypair, priv_path: Path, pub_path: Path) -> None:
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    priv_bytes = keypair.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = keypair.public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path.write_bytes(priv_bytes)
    pub_path.write_bytes(pub_bytes)

def load_private_key(path: Path) -> Ed25519PrivateKey:
    return serialization.load_pem_private_key(path.read_bytes(), password=None)

def load_public_key(path: Path) -> Ed25519PublicKey:
    return serialization.load_pem_public_key(path.read_bytes())

def load_or_create(priv_path: Path, pub_path: Path) -> Ed25519Keypair:
    if priv_path.exists() and pub_path.exists():
        priv = load_private_key(priv_path)
        pub = load_public_key(pub_path)
        assert isinstance(priv, Ed25519PrivateKey)
        assert isinstance(pub, Ed25519PublicKey)
        return Ed25519Keypair(private_key=priv, public_key=pub)
    kp = generate_keypair()
    save_keypair(kp, priv_path, pub_path)
    return kp
