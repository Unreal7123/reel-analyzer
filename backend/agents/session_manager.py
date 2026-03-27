"""
Session Manager
==============

Reads Instagram session cookies and Facebook API credentials from environment
variables and converts them into the format Playwright and httpx expect.

Environment variables (all optional):
--------------------------------------
INSTAGRAM_SESSIONID      Your Instagram sessionid cookie value
INSTAGRAM_CSRFTOKEN      Your Instagram csrftoken cookie value
INSTAGRAM_DS_USER_ID     Your Instagram ds_user_id cookie value
INSTAGRAM_MID            Your Instagram mid cookie value
INSTAGRAM_IG_DID         Your Instagram ig_did cookie value

FACEBOOK_ACCESS_TOKEN    Facebook Graph API access token (for oEmbed API)

How to obtain Instagram session cookies
----------------------------------------
1. Log into Instagram in Chrome
2. Open DevTools (F12) → Application → Cookies → https://www.instagram.com
3. Copy the values for: sessionid, csrftoken, ds_user_id, mid, ig_did
4. Set each as an environment variable (see .env.example)

IMPORTANT: These are YOUR OWN session cookies.  ReelScan uses them to
authenticate your scraping requests exactly as your browser would.
Do NOT share your sessionid with anyone.

None of these vars are required — the scraper falls back gracefully through
Tier 2 (curl-cffi) and Tier 3 (oEmbed) when no session is configured.
"""

from __future__ import annotations
import os
import logging

logger = logging.getLogger(__name__)

# Cookie domain used by Playwright's add_cookies()
_INSTAGRAM_DOMAIN = ".instagram.com"


def get_instagram_cookies() -> list[dict]:
    """
    Build a Playwright-compatible cookie list from environment variables.
    Returns an empty list if no cookies are configured.
    """
    mapping = {
        "INSTAGRAM_SESSIONID":   "sessionid",
        "INSTAGRAM_CSRFTOKEN":   "csrftoken",
        "INSTAGRAM_DS_USER_ID":  "ds_user_id",
        "INSTAGRAM_MID":         "mid",
        "INSTAGRAM_IG_DID":      "ig_did",
    }

    cookies: list[dict] = []
    for env_var, cookie_name in mapping.items():
        value = os.getenv(env_var, "").strip()
        if value:
            cookies.append({
                "name":     cookie_name,
                "value":    value,
                "domain":   _INSTAGRAM_DOMAIN,
                "path":     "/",
                "httpOnly": cookie_name == "sessionid",
                "secure":   True,
                "sameSite": "Lax",
            })

    if cookies:
        names = [c["name"] for c in cookies]
        logger.info("Session cookies configured: %s", names)
        if "sessionid" not in names:
            logger.warning(
                "sessionid not set — authenticated scraping will not work. "
                "Set INSTAGRAM_SESSIONID in environment variables."
            )
    else:
        logger.info(
            "No session cookies configured — using anonymous scraping. "
            "Set INSTAGRAM_SESSIONID (and others) in .env for better results."
        )

    return cookies


def has_session() -> bool:
    """Return True if at minimum a sessionid cookie is configured."""
    return bool(os.getenv("INSTAGRAM_SESSIONID", "").strip())


def get_facebook_token() -> str:
    """Return the Facebook Graph API access token, or empty string."""
    token = os.getenv("FACEBOOK_ACCESS_TOKEN", "").strip()
    if token:
        logger.debug("Facebook access token configured")
    return token


def session_status() -> dict:
    """
    Return a dict describing the current session configuration.
    Used by the /health and /session-status endpoints.
    """
    cookies   = get_instagram_cookies()
    has_fb    = bool(get_facebook_token())
    cookie_names = [c["name"] for c in cookies]

    return {
        "instagram_cookies_configured": bool(cookies),
        "has_sessionid":     "sessionid"  in cookie_names,
        "has_csrftoken":     "csrftoken"  in cookie_names,
        "has_ds_user_id":    "ds_user_id" in cookie_names,
        "facebook_token":    has_fb,
        "scrape_tier_available": (
            "playwright_authenticated" if ("sessionid" in cookie_names) else
            "playwright_anonymous"     if True else
            "oembed_only"
        ),
        "recommendation": (
            "Fully configured — best data quality expected."
            if ("sessionid" in cookie_names)
            else
            "INSTAGRAM_SESSIONID not set. "
            "Scraping will use anonymous Playwright + oEmbed fallback. "
            "Set session cookies in .env for reliable caption extraction."
        ),
    }
