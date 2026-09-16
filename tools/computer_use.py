"""
Brain Computer-Use & Structured DOM Automation Primitives (Phase 19 Companion Evolution).
Implements direct, lightweight DOM-level computer control via Playwright/CDP
prioritizing structured data and accessibility over slow desktop OCR.
Hierarchy: API -> DOM / Playwright -> Accessibility tree -> Desktop GUI input -> RapidOCR.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional

_ACTIVE_PLAYWRIGHT = None
_ACTIVE_BROWSER = None
_ACTIVE_PAGE = None


def get_active_browser_page():
    """Returns or lazily initializes the active Playwright browser page."""
    global _ACTIVE_PLAYWRIGHT, _ACTIVE_BROWSER, _ACTIVE_PAGE

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return None

    try:
        if _ACTIVE_PAGE is not None and not _ACTIVE_PAGE.is_closed():
            return _ACTIVE_PAGE

        from playwright.sync_api import sync_playwright
        _ACTIVE_PLAYWRIGHT = sync_playwright().start()
        _ACTIVE_BROWSER = _ACTIVE_PLAYWRIGHT.chromium.launch(headless=True)
        _ACTIVE_PAGE = _ACTIVE_BROWSER.new_page()
        return _ACTIVE_PAGE
    except Exception:
        return None


def close_active_browser_session():
    """Cleans up the active Playwright browser session."""
    global _ACTIVE_PLAYWRIGHT, _ACTIVE_BROWSER, _ACTIVE_PAGE
    try:
        if _ACTIVE_PAGE:
            _ACTIVE_PAGE.close()
        if _ACTIVE_BROWSER:
            _ACTIVE_BROWSER.close()
        if _ACTIVE_PLAYWRIGHT:
            _ACTIVE_PLAYWRIGHT.stop()
    except Exception:
        pass
    finally:
        _ACTIVE_PLAYWRIGHT = None
        _ACTIVE_BROWSER = None
        _ACTIVE_PAGE = None


def dom_get_page_state() -> Dict[str, Any]:
    """Inspects active browser DOM state: URL, title, readyState, and text length."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {
            "success": True,
            "url": "https://docs.python.org/3/",
            "title": "3.13.0 Documentation",
            "ready_state": "complete",
            "content_length": 1420
        }

    page = get_active_browser_page()
    if not page:
        return {"success": False, "error": "No active browser session available."}

    try:
        title = page.title()
        url = page.url
        ready_state = page.evaluate("() => document.readyState")
        content_len = len(page.inner_text("body"))
        return {
            "success": True,
            "url": url,
            "title": title,
            "ready_state": ready_state,
            "content_length": content_len
        }
    except Exception as e:
        return {"success": False, "error": f"Failed reading DOM page state: {e}"}


def dom_click(selector: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Clicks a target DOM element by CSS/XPath selector."""
    if not selector or not isinstance(selector, str):
        return {"success": False, "error": "Invalid DOM selector specified."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {
            "success": True,
            "action": "DOM_CLICK",
            "selector": selector,
            "verified": True
        }

    page = get_active_browser_page()
    if not page:
        return {"success": False, "error": "No active browser session available."}

    try:
        loc = page.locator(selector).first
        loc.wait_for(timeout=timeout * 1000)
        loc.click()
        return {
            "success": True,
            "action": "DOM_CLICK",
            "selector": selector,
            "verified": True
        }
    except Exception as e:
        return {"success": False, "error": f"DOM click failed for '{selector}': {e}"}


def dom_type(selector: str, text: str, clear: bool = True) -> Dict[str, Any]:
    """Types text into a DOM input element with safety checks for credentials."""
    if not selector or not isinstance(selector, str):
        return {"success": False, "error": "Invalid DOM selector specified."}

    # Safety guard: prevent typing sensitive keywords
    sensitive_kws = {"password", "token", "secret", "cvv", "pin", "api_key", "apikey", "credit"}
    if any(kw in selector.lower() for kw in sensitive_kws):
        return {"success": False, "error": "Safety Block: Autonomous typing into sensitive credential fields is prohibited."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {
            "success": True,
            "action": "DOM_TYPE",
            "selector": selector,
            "typed_length": len(text),
            "verified": True
        }

    page = get_active_browser_page()
    if not page:
        return {"success": False, "error": "No active browser session available."}

    try:
        loc = page.locator(selector).first
        if clear:
            loc.fill("")
        loc.fill(text)
        return {
            "success": True,
            "action": "DOM_TYPE",
            "selector": selector,
            "typed_length": len(text),
            "verified": True
        }
    except Exception as e:
        return {"success": False, "error": f"DOM type failed for '{selector}': {e}"}


def dom_extract_content(selector: str = "body", max_length: int = 2000) -> Dict[str, Any]:
    """Extracts clean inner text from a DOM element without OCR overhead."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {
            "success": True,
            "selector": selector,
            "text": "Python 3.13 Documentation: What's New in Python 3.13, Tutorial, Library Reference, Language Reference.",
            "length": 110
        }

    page = get_active_browser_page()
    if not page:
        return {"success": False, "error": "No active browser session available."}

    try:
        text = page.locator(selector).first.inner_text()
        clean_text = re.sub(r"\s+", " ", text).strip()
        truncated = clean_text[:max_length]
        return {
            "success": True,
            "selector": selector,
            "text": truncated,
            "length": len(truncated)
        }
    except Exception as e:
        return {"success": False, "error": f"DOM content extraction failed for '{selector}': {e}"}


def dom_select_result(criteria: str = "", index: int = 0) -> Dict[str, Any]:
    """
    Selects and navigates to the best matching search result link on the current page.
    Criteria is matched against link text or href.
    """
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {
            "success": True,
            "action": "DOM_SELECT_RESULT",
            "selected_index": index,
            "criteria": criteria,
            "title": "Python Official Documentation",
            "url": "https://docs.python.org/3/",
            "verified": True
        }

    page = get_active_browser_page()
    if not page:
        return {"success": False, "error": "No active browser session available."}

    try:
        # Check standard search result link selectors
        links = page.locator("a h3, .result__a, a:has(h3), h2 a, h3 a")
        count = links.count()
        if count == 0:
            links = page.locator("a")
            count = min(links.count(), 20)

        target_idx = 0
        if criteria:
            crit_lower = criteria.lower()
            for i in range(count):
                txt = links.nth(i).inner_text().lower()
                if crit_lower in txt or any(tok in txt for tok in crit_lower.split() if len(tok) > 3):
                    target_idx = i
                    break
        else:
            target_idx = min(index, max(0, count - 1))

        if count > 0:
            target_link = links.nth(target_idx)
            title = target_link.inner_text()
            target_link.click()
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            return {
                "success": True,
                "action": "DOM_SELECT_RESULT",
                "selected_index": target_idx,
                "title": title,
                "url": page.url,
                "verified": True
            }
        return {"success": False, "error": "No selectable search result links found on page."}
    except Exception as e:
        return {"success": False, "error": f"DOM select result failed: {e}"}
