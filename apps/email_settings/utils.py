

import imaplib
import smtplib
import socket
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone

# Provider auto-configuration
PROVIDER_DEFAULTS = {
    'gmail': {
        'imap_server': 'imap.gmail.com',
        'imap_port': 993,
        'imap_ssl': True,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'smtp_ssl_implicit': False,
    },
    'outlook': {
        'imap_server': 'outlook.office365.com',
        'imap_port': 993,
        'imap_ssl': True,
        'smtp_server': 'smtp.office365.com',
        'smtp_port': 587,
        'smtp_ssl_implicit': False,
    },
    'yahoo': {
        'imap_server': 'imap.mail.yahoo.com',
        'imap_port': 993,
        'imap_ssl': True,
        'smtp_server': 'smtp.mail.yahoo.com',
        'smtp_port': 465,
        'smtp_ssl_implicit': True,
    },
    'custom': {
        'imap_server': '',
        'imap_port': 993,
        'imap_ssl': True,
        'smtp_server': '',
        'smtp_port': 587,
        'smtp_ssl_implicit': False,
    }
}

@dataclass
class ConnectionResult:
    success: bool
    message: str
    details: Dict[str, Any]

def _get_fernet() -> Fernet:
    key = getattr(settings, 'EMAIL_CREDENTIAL_KEY', None)
    if not key:
        # Fallback for dev if key is missing, BUT strictly warn in logs
        print("WARNING: EMAIL_CREDENTIAL_KEY not set. Generating temporary key.")
        return Fernet(Fernet.generate_key())
    return Fernet(key.encode() if isinstance(key, str) else key)

def encrypt_credential(plaintext: str) -> str:
    if not plaintext: return ""
    f = _get_fernet()
    token = f.encrypt(plaintext.encode())
    return token.decode()

def decrypt_credential(token: str) -> str:
    if not token: return ""
    f = _get_fernet()
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        raise ValueError("Decryption failed")

def apply_provider_defaults(account_obj) -> None:
    provider_key = (account_obj.email_provider or 'custom').lower()
    defaults = PROVIDER_DEFAULTS.get(provider_key, PROVIDER_DEFAULTS['custom'])

    if not account_obj.imap_server: account_obj.imap_server = defaults['imap_server']
    if not account_obj.imap_port: account_obj.imap_port = defaults['imap_port']
    if not account_obj.smtp_server: account_obj.smtp_server = defaults['smtp_server']
    if not account_obj.smtp_port: account_obj.smtp_port = defaults['smtp_port']

def normalize_and_get_credential(account_obj, decrypt: bool = True) -> str:
    raw = account_obj.access_credential or ""
    # Remove spaces (fix for the copy-paste issue)
    candidate = "".join(raw.split()) 
    
    if not candidate:
        return ""
    
    if decrypt:
        # Try to decrypt; if it fails, assume it's raw text
        try:
            return decrypt_credential(candidate)
        except Exception:
            return candidate
    return candidate

# ---------- Transport abstraction ----------
class EmailTransport:
    def __init__(self, imap_server, imap_port, smtp_server, smtp_port,
                 email_address, credential, use_ssl_tls=True,
                 smtp_implicit_ssl=None, timeout=10):
        self.imap_server = imap_server
        self.imap_port = int(imap_port) if imap_port else None
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port) if smtp_port else None
        self.email_address = email_address
        self.credential = credential
        self.use_ssl_tls = bool(use_ssl_tls)
        self.smtp_implicit_ssl = smtp_implicit_ssl
        self.timeout = timeout

    def check_imap(self) -> ConnectionResult:
        try:
            if self.use_ssl_tls:
                M = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, timeout=self.timeout)
            else:
                M = imaplib.IMAP4(self.imap_server, self.imap_port, timeout=self.timeout)
            
            M.login(self.email_address, self.credential)
            M.select('INBOX')
            M.logout()
            return ConnectionResult(True, "IMAP connection successful.", {})
        except Exception as e:
            return ConnectionResult(False, f"IMAP Error: {str(e)}", {"error": str(e)})

    def check_smtp(self) -> ConnectionResult:
        try:
            implicit_ssl = self.smtp_implicit_ssl if self.smtp_implicit_ssl is not None else self.use_ssl_tls
            
            if implicit_ssl and self.smtp_port == 465:
                S = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=self.timeout)
            else:
                S = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.timeout)
                if not implicit_ssl:
                    try:
                        if S.has_extn('STARTTLS'):
                            S.starttls()
                            S.ehlo()
                    except Exception:
                        pass # Best effort

            S.ehlo()
            S.login(self.email_address, self.credential)
            S.quit()
            return ConnectionResult(True, "SMTP connection successful.", {})
        except Exception as e:
            return ConnectionResult(False, f"SMTP Error: {str(e)}", {"error": str(e)})

def test_account_connection(account_instance) -> Dict[str, Any]:
    apply_provider_defaults(account_instance)
    
    # Decrypt credential
    credential = normalize_and_get_credential(account_instance, decrypt=True)
    
    if not credential:
        return {"success": False, "imap_status": "No credential found.", "smtp_status": "No credential found."}

    transport = EmailTransport(
        imap_server=account_instance.imap_server,
        imap_port=account_instance.imap_port,
        smtp_server=account_instance.smtp_server,
        smtp_port=account_instance.smtp_port,
        email_address=account_instance.email_address,
        credential=credential,
        use_ssl_tls=account_instance.use_ssl_tls
    )

    imap_res = transport.check_imap()
    smtp_res = transport.check_smtp()

    return {
        "success": imap_res.success and smtp_res.success,
        "imap_status": imap_res.message,
        "smtp_status": smtp_res.message,
        "diagnostics": {
            "imap": imap_res.details,
            "smtp": smtp_res.details
        }
    }