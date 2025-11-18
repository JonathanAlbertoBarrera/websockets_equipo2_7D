"""
Script para generar certificados SSL autofirmados para desarrollo local
"""
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime
import ipaddress

def generate_self_signed_cert():
    """Genera un certificado SSL autofirmado"""
    
    # Generar clave privada
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Información del certificado
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "MX"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Estado"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Ciudad"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Chat WebSocket Dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    
    # Crear certificado
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("127.0.0.1"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    
    # Guardar clave privada
    with open("ssl_cert.key", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Guardar certificado
    with open("ssl_cert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    print(" Certificados SSL generados exitosamente:")
    print("   - ssl_cert.key (Clave privada)")
    print("   - ssl_cert.pem (Certificado)")
    print("\n  IMPORTANTE: Estos son certificados para DESARROLLO solamente.")
    print("   Para producción, se usan certificados válidos (ej: Let's Encrypt)")

if __name__ == "__main__":
    generate_self_signed_cert()
