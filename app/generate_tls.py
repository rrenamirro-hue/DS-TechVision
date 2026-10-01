"""Genera una CA local y un certificado TLS con SAN para una IP privada."""
import argparse
import ipaddress
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _private_ip(value: str) -> ipaddress.IPv4Address:
    address = ipaddress.ip_address(value)
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_private or address.is_loopback:
        raise argparse.ArgumentTypeError('Debe ser una IPv4 privada de la LAN (no 127.0.0.1)')
    return address


def default_output() -> Path:
    root = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / '.ds_techvision'))
    return root / 'DataSystems' / 'DS_TechVision' / 'certs'


def _write_private(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def certificate_matches(path: Path, address: ipaddress.IPv4Address) -> bool:
    if not path.is_file():
        return False
    try:
        cert = x509.load_pem_x509_certificate(path.read_bytes())
        sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        cert.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
        return address in sans.get_values_for_type(x509.IPAddress) and cert.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=30)
    except (ValueError, x509.ExtensionNotFound):
        return False


def generate(address: ipaddress.IPv4Address, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    server_cert_path = output / 'server-cert.pem'
    if certificate_matches(server_cert_path, address) and (output / 'server-key.pem').is_file() and (output / 'ca-cert.cer').is_file():
        print(f'TLS_CERT_EXISTS={server_cert_path}')
        return
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'DataSystems'), x509.NameAttribute(NameOID.COMMON_NAME, 'DS TechVision Local CA')])
    ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False).add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=False, content_commitment=False, data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True).sign(ca_key, hashes.SHA256()))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    server_name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'DataSystems'), x509.NameAttribute(NameOID.COMMON_NAME, str(address))])
    server_cert = (x509.CertificateBuilder().subject_name(server_name).issuer_name(ca_name).public_key(server_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=825)).add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()), critical=False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False).add_extension(x509.SubjectAlternativeName([x509.IPAddress(address), x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False).add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=True, content_commitment=False, data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True).sign(ca_key, hashes.SHA256()))
    _write_private(output / 'ca-key.pem', ca_key); _write_private(output / 'server-key.pem', server_key)
    (output / 'ca-cert.pem').write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    (output / 'ca-cert.cer').write_bytes(ca_cert.public_bytes(serialization.Encoding.DER))
    server_cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    print(f'TLS_CERT_CREATED={server_cert_path}'); print(f'ANDROID_CA_CERT={output / "ca-cert.cer"}')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--ip', required=True, type=_private_ip); parser.add_argument('--output', type=Path, default=default_output()); args = parser.parse_args(); generate(args.ip, args.output)


if __name__ == '__main__':
    main()
