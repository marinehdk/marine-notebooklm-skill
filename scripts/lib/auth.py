import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path


def _storage_state_path() -> Path:
    return Path.home() / ".notebooklm" / "storage_state.json"


def is_authenticated() -> bool:
    """Check if user has valid NotebookLM authentication (must have SID cookie)."""
    path = _storage_state_path()
    if not path.exists():
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        cookies = data.get("cookies", [])
        names = {c["name"] for c in cookies}
        return "SID" in names
    except Exception:
        return False


def assert_authenticated() -> None:
    """Exit with helpful message if not authenticated."""
    if not is_authenticated():
        print(
            "❌ Not authenticated with Google.\n"
            "Run: bash $HOME/.claude/skills/nlm/scripts/invoke.sh setup --auth"
        )
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Chrome cookie extraction (macOS)
# ---------------------------------------------------------------------------

_CHROME_PROFILES = [
    Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
    Path.home() / "Library/Application Support/Google/Chrome/Profile 1/Cookies",
    Path.home() / "Library/Application Support/Chromium/Default/Cookies",
    Path.home() / "Library/Application Support/Microsoft Edge/Default/Cookies",
]

_GOOGLE_DOMAINS = {
    ".google.com", "google.com", "accounts.google.com",
    "notebooklm.google.com", ".google.com.hk", ".google.com.cn",
}


def _get_chrome_key() -> bytes:
    """Derive AES key from Chrome Safe Storage Keychain entry."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    import base64

    result = subprocess.run(
        ["security", "find-generic-password", "-a", "Chrome", "-s", "Chrome Safe Storage", "-w"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        # Try Edge
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "Microsoft Edge", "-s", "Microsoft Edge Safe Storage", "-w"],
            capture_output=True, text=True, timeout=10,
        )
    password = result.stdout.strip().encode() if result.returncode == 0 else b"peanuts"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=16,
        salt=b"saltysalt",
        iterations=1003,
    )
    return kdf.derive(password)


def _decrypt_cookie(encrypted: bytes, key: bytes) -> str:
    """Decrypt a Chrome v10/v11 AES-CBC cookie value."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    if encrypted[:3] == b"v10" or encrypted[:3] == b"v11":
        encrypted = encrypted[3:]

    iv = b" " * 16
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypted) + decryptor.finalize()
    # Remove PKCS7 padding
    pad_len = decrypted[-1]
    return decrypted[:-pad_len].decode("utf-8", errors="replace")


def import_cookies_from_chrome() -> dict:
    """
    Extract Google cookies from the local Chrome profile and write to
    ~/.notebooklm/storage_state.json. Returns the storage state dict.
    """
    db_path = next((p for p in _CHROME_PROFILES if p.exists()), None)
    if db_path is None:
        raise RuntimeError(
            "Chrome cookies database not found.\n"
            "Ensure Chrome (or Edge) is installed and you have logged in to Google."
        )

    key = _get_chrome_key()

    # Copy DB to avoid SQLite lock from running Chrome
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    shutil.copy2(db_path, tmp_path)

    cookies = []
    try:
        con = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        cur = con.execute(
            "SELECT host_key, name, encrypted_value, path, expires_utc, is_httponly, is_secure, samesite "
            "FROM cookies WHERE host_key LIKE '%.google.com%' OR host_key = 'accounts.google.com'"
        )
        for host, name, enc_val, path, expires, httponly, secure, samesite in cur:
            try:
                value = _decrypt_cookie(enc_val, key)
            except Exception:
                continue  # skip undecryptable cookies

            samesite_map = {-1: "Unspecified", 0: "None", 1: "Lax", 2: "Strict"}
            cookies.append({
                "name": name,
                "value": value,
                "domain": host,
                "path": path,
                "expires": expires / 1_000_000 - 11644473600 if expires else -1,
                "httpOnly": bool(httponly),
                "secure": bool(secure),
                "sameSite": samesite_map.get(samesite, "Lax"),
            })
        con.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    if not any(c["name"] == "SID" for c in cookies):
        raise RuntimeError(
            "SID cookie not found in Chrome.\n"
            "Please open Chrome, go to https://notebooklm.google.com, and log in first."
        )

    storage_state = {"cookies": cookies, "origins": []}
    out = _storage_state_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(storage_state, f, indent=2)

    sid_count = sum(1 for c in cookies if c["name"] == "SID")
    return {"cookies_imported": len(cookies), "sid_found": sid_count, "path": str(out)}
