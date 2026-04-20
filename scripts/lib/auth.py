import json
import time
import re
import shutil
from pathlib import Path


def _storage_state_path() -> Path:
    return Path.home() / ".notebooklm" / "storage_state.json"


def _browser_profile_dir() -> Path:
    return Path.home() / ".notebooklm" / "chrome_profile"


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
            "Not authenticated with Google.\n"
            "Run: bash $HOME/.claude/skills/nlm/scripts/invoke.sh setup --auth"
        )
        raise SystemExit(1)


def import_cookies_from_browser(timeout_minutes: int = 5) -> dict:
    """
    Open real Chrome browser, navigate to NotebookLM, wait for login,
    then save storage state. Uses patchright with channel='chrome' to
    launch the user's installed Chrome (not Playwright's Chromium),
    so existing Google sessions are preserved.

    Returns dict with cookies_imported count and path.
    """
    from patchright.sync_api import sync_playwright

    out_path = _storage_state_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = _browser_profile_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)

    playwright = None
    context = None
    try:
        playwright = sync_playwright().start()

        # Launch real Chrome with persistent profile (bypasses bot detection).
        # If the user is already logged into Chrome, they won't need to re-enter credentials.
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )

        # Inject existing cookies so session is restored even if storage_state
        # wasn't saved from a previous Chrome session.
        if out_path.exists():
            try:
                with open(out_path) as f:
                    existing = json.load(f)
                if existing.get("cookies"):
                    context.add_cookies(existing["cookies"])
            except Exception:
                pass

        page = context.new_page()
        page.goto("https://notebooklm.google.com", wait_until="domcontentloaded")

        # If already on NotebookLM (not redirected to accounts.google.com), skip login
        if "accounts.google.com" not in page.url:
            print("Already logged in — saving session state...", flush=True)
        else:
            print(
                f"Chrome opened. Please log in with your Google account.\n"
                f"Waiting up to {timeout_minutes} minutes...",
                flush=True,
            )
            timeout_ms = int(timeout_minutes * 60 * 1000)
            page.wait_for_url(
                re.compile(r"^https://notebooklm\.google\.com/"),
                timeout=timeout_ms,
            )
            print("Login detected — saving session state...", flush=True)

        # Save storage state (cookies + localStorage)
        context.storage_state(path=str(out_path))

        with open(out_path) as f:
            saved = json.load(f)
        cookies = saved.get("cookies", [])
        sid_count = sum(1 for c in cookies if c["name"] == "SID")

        if sid_count == 0:
            raise RuntimeError(
                "SID cookie not found after login.\n"
                "Make sure you completed the Google login in the Chrome window."
            )

        return {
            "cookies_imported": len(cookies),
            "sid_found": sid_count,
            "path": str(out_path),
        }

    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass


def clear_auth() -> None:
    """Remove stored auth state and browser profile."""
    path = _storage_state_path()
    if path.exists():
        path.unlink()
    profile_dir = _browser_profile_dir()
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
