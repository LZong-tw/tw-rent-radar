"""Facebook session management with Playwright.

Saves browser state to fb_session/ so subsequent crawls reuse the login.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import BrowserContext, Playwright

FB_SESSION_DIR = Path("fb_session")
_STATE_FILE = FB_SESSION_DIR / "state.json"


async def _session_is_valid(context: BrowserContext) -> bool:
    """Navigate to facebook.com and check if the session is still logged in."""
    page = await context.new_page()
    try:
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        # If we end up on /login or the login form is visible, session is invalid.
        if "/login" in page.url:
            return False
        # Additional heuristic: look for the login email field
        login_field = await page.query_selector('input[name="email"]')
        return login_field is None
    finally:
        await page.close()


async def _prompt_manual_login(context: BrowserContext) -> None:
    """Open a visible browser page and wait for the user to log in manually."""
    page = await context.new_page()
    await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
    print("\n===== Facebook Login Required =====")
    print("A browser window has opened. Please log in to Facebook manually.")
    print("After you have logged in and see the News Feed, come back here")
    print("and press ENTER to continue.")
    print("===================================\n")
    # Run input() in a thread so it doesn't block the event loop.
    await asyncio.get_event_loop().run_in_executor(None, input)
    await page.close()


async def ensure_fb_session(pw: Playwright) -> BrowserContext:
    """Return a Playwright *BrowserContext* with an active Facebook session.

    * If ``fb_session/state.json`` exists and the session is valid, the
      context is loaded from that file (headless).
    * Otherwise a visible browser is launched and the user is asked to log in
      manually.  Once they press ENTER the storage state is persisted for
      future runs.
    """
    FB_SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # Try to reuse a previously saved session.
    if _STATE_FILE.exists():
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(_STATE_FILE))
        if await _session_is_valid(context):
            return context
        # Session expired – close and fall through to manual login.
        await context.close()
        await browser.close()

    # No valid session – ask the user to log in.
    browser = await pw.chromium.launch(headless=False)
    context = await browser.new_context()
    await _prompt_manual_login(context)

    # Persist the session for next time.
    await context.storage_state(path=str(_STATE_FILE))
    return context
