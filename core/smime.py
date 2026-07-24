# -*- coding: utf-8 -*-
"""S/MIME digital signature support."""
import os
import base64
from datetime import datetime, timedelta
from typing import Optional, Tuple

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12

from .config import BASE_DIR, logger

SMIME_CERT_FILE = BASE_DIR / "smime_cert.p12"


def generate_smime_cert(common_name: str = "LeadGen S/MIME", validity_days: int = 365) -> Tuple[bytes, str]:
    """
    Generuje certyfikat S/MIME (SHA256/RSA, 2048-bit).
    Zwraca (p12_bytes, fingerprint).
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LeadGen"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
    ])
    issuer = subject

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    p12 = pkcs12.serialize_key_and_certificates(
        name=None,
        key=private_key,
        cert=certificate,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"")
    )

    finger = certificate.fingerprint(hashes.SHA256()).hex()[:16]

    SMIME_CERT_FILE.write_bytes(p12)
    logger.info("Wygenerowano certyfikat S/MIME, fingerprint: %s", finger)
    return p12, finger


def load_smime_cert() -> Optional[Tuple[rsa.RSAPrivateKey, x509.Certificate]]:
    if not SMIME_CERT_FILE.exists():
        return None
    try:
        p12_data = SMIME_CERT_FILE.read_bytes()
        private_key, certificate, _ = pkcs12.load_key_and_certificates(
            p12_data,
            password=None
        )
        return private_key, certificate
    except Exception as e:
        logger.warning("Nie udało się załadować certyfikatu S/MIME: %s", e)
        return None


def sign_email_content(content: bytes) -> Optional[bytes]:
    """Podpisuje zawartość e-maila (już zakodowaną), zwraca podpis binarny."""
    cert = load_smime_cert()
    if not cert:
        return None
    private_key, _ = cert
    try:
        signature = private_key.sign(
            content,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return signature
    except Exception as e:
        logger.error("Błąd podpisywania S/MIME: %s", e)
        return None
