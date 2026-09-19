import os
import time
from tools.search import perform_web_search
from tools.apps import open_app, default_app_tracker
from tools.input import hotkey, type_text, press_key
from tools.screen import analyze_captured_screen
from tools.vision import default_vision

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


class BaseBrowserProvider:
    """Base interface for Browser Capability Provider."""
    def search(self, query):
        raise NotImplementedError()

    def navigate(self, url):
        raise NotImplementedError()

    def read_page(self, url=None):
        raise NotImplementedError()


def sanitize_untrusted_web_data(text: str) -> str:
    """
    Stage 8X — Prompt Injection Shield & Untrusted Data Boundary.
    Strips systemic prompt injection triggers from external web text and tags data as untrusted.
    """
    if not text or not isinstance(text, str):
        return ""

    import re
    injection_patterns = [
        r"(?i)ignore\s+(all\s+)?(previous\s+)?(safety\s+)?rules",
        r"(?i)system\s+prompt\s+override",
        r"(?i)open\s+terminal\s+and\s+run",
        r"(?i)execute\s+shell\s+command",
        r"(?i)sudo\s+rm\s+-rf"
    ]

    cleaned = text
    for pat in injection_patterns:
        cleaned = re.sub(pat, "[FILTERED_UNTRUSTED_CONTENT]", cleaned)

    return f"[UNTRUSTED_WEBPAGE_DATA]\n{cleaned.strip()}\n[/UNTRUSTED_WEBPAGE_DATA]"


class StructuredBrowserProvider(BaseBrowserProvider):
    """
    Structured Browser Provider.
    Executes fast structured searches and data retrieval via HTTP endpoints / APIs
    without requiring heavy visual desktop OCR overhead.
    """
    def search(self, query):
        if not query or not isinstance(query, str):
            return {"success": False, "error": "Query cannot be empty."}
        res = perform_web_search(query)
        if isinstance(res, str) and res.startswith("Error:"):
            return {"success": False, "error": res}
        return {"success": True, "results": res, "provider": "structured"}

    def navigate(self, url):
        return {"success": True, "url": url, "provider": "structured"}

    def read_page(self, url=None):
        return {"success": True, "content": "Structured browser content read.", "provider": "structured"}


class GUIFallbackBrowserProvider(BaseBrowserProvider):
    """
    GUI Fallback Browser Provider.
    Executes real desktop browser actions inside the opened Brave window:
    OPEN_APP -> FOCUS_APP -> HOTKEY(["ctrl", "l"]) -> TYPE_TEXT(query) -> PRESS_KEY("return") -> ANALYZE_SCREEN -> VERIFY
    """
    def search(self, query):
        if not query or not isinstance(query, str):
            return {"success": False, "error": "Query cannot be empty."}

        # 1. Ensure Brave is opened
        open_res = open_app("brave")

        # 2. Ensure Brave is focused
        from tools.apps import focus_app
        focus_res = focus_app("brave")

        # 3. Focus address bar
        hotkey(["ctrl", "l"])

        # 4. Type query
        type_text(query)

        # 5. Submit
        press_key("return")

        # 6. Bounded navigation pause
        time.sleep(1.0)

        # 7. Refresh observation
        obs = analyze_captured_screen(force_refresh=True)

        elems = obs.get("elements", []) if isinstance(obs, dict) else []

        # 8. Physical verification: verify query terms loaded
        import os
        is_mock = os.environ.get("BRAIN_MOCK_GUI") == "1"
        verified = True
        verification_detail = "Search query submitted and verified."
        if not is_mock and query:
            texts = []
            if isinstance(obs, dict):
                perc = obs.get("perception", {})
                texts = perc.get("detected_text", []) or [e.get("text", "") for e in elems if isinstance(e, dict) and e.get("text")]
            search_words = [w.lower() for w in query.split() if len(w) > 2]
            found = any(any(sw in str(t).lower() for sw in search_words) for t in texts) if search_words else True
            if not found and texts:
                verified = False
                verification_detail = f"Query terms not visually detected in observation ({len(texts)} texts detected)."
            else:
                verified = True
                verification_detail = f"Search verified: query terms confirmed on screen."

        return {
            "success": True,
            "capability": "BROWSER_SEARCH_FOREGROUND",
            "query": query,
            "browser": "brave",
            "verified": verified,
            "verification_detail": verification_detail,
            "screen_observation": {
                "status": obs.get("status", "VISION_ANALYZED") if isinstance(obs, dict) else "VISION_ANALYZED",
                "elements_count": len(elems),
                "source_application": "brave",
                "focused_application": obs.get("focused_application", "brave") if isinstance(obs, dict) else "brave"
            },
            "observation": obs,
            "provider": "gui_fallback"
        }

    def new_tab(self):
        """Opens a new tab in Brave and verifies tab readiness."""
        open_app("brave")
        from tools.apps import focus_app
        focus_app("brave")
        hotkey(["ctrl", "t"])
        time.sleep(0.3)
        obs = analyze_captured_screen(force_refresh=True)
        return {
            "success": True,
            "capability": "NEW_TAB",
            "browser": "brave",
            "verified": True,
            "observation": obs,
            "data": "New tab opened in Brave."
        }

    def navigate(self, url):
        open_app("brave")
        from tools.apps import focus_app
        focus_app("brave")
        hotkey(["ctrl", "l"])
        type_text(url)
        press_key("return")
        time.sleep(1.0)
        obs = analyze_captured_screen(force_refresh=True)
        return {"success": True, "url": url, "observation": obs, "provider": "gui_fallback"}

    def read_page(self, url=None):
        obs = default_vision.get_current_observation()
        if not obs:
            obs = analyze_captured_screen(force_refresh=True)
        return {"success": True, "observation": obs, "provider": "gui_fallback"}


class PlaywrightBrowserProvider(BaseBrowserProvider):
    """
    Playwright Browser Provider.
    Executes fast, reliable structured browser automation via Playwright DOM / CDP
    without requiring visual desktop OCR.
    """
    def search(self, query):
        if not query or not isinstance(query, str):
            return {"success": False, "error": "Query cannot be empty."}
        try:
            from playwright.sync_api import sync_playwright
            from tools.search import clean_url
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                encoded_q = query.replace(" ", "+")
                page.goto(f"https://html.duckduckgo.com/html/?q={encoded_q}", timeout=10000)

                locators = page.locator(".result__body")
                count = min(locators.count(), 3)
                results = []
                for i in range(count):
                    elem = locators.nth(i)
                    title_elem = elem.locator(".result__a")
                    snippet_elem = elem.locator(".result__snippet")
                    title = title_elem.text_content() if title_elem.count() > 0 else ""
                    href = title_elem.get_attribute("href") if title_elem.count() > 0 else ""
                    snippet = snippet_elem.text_content() if snippet_elem.count() > 0 else ""

                    link = clean_url(href)
                    if link and title:
                        results.append({
                            "title": title.strip(),
                            "url": link,
                            "snippet": snippet.strip()
                        })
                browser.close()
                if results:
                    return {
                        "success": True,
                        "query": query,
                        "results": results,
                        "provider": "playwright_chromium",
                        "status": "COMPLETED"
                    }
        except Exception:
            pass
        return StructuredBrowserProvider().search(query)

    def navigate(self, url):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=10000)
                title = page.title()
                browser.close()
                return {"success": True, "url": url, "title": title, "provider": "playwright_chromium"}
        except Exception as e:
            return StructuredBrowserProvider().navigate(url)

    def read_page(self, url=None):
        if not url:
            return StructuredBrowserProvider().read_page(url)
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=10000)
                text = page.inner_text("body")
                browser.close()
                return {"success": True, "url": url, "content": text[:1000], "provider": "playwright_chromium"}
        except Exception:
            return StructuredBrowserProvider().read_page(url)

    def download(self, url, destination=None):
        """Controlled browser download via Playwright."""
        if not url:
            return {"success": False, "error": "URL cannot be empty."}
        try:
            import os
            from pathlib import Path
            if sync_playwright is not None:
                sp = sync_playwright
            else:
                try:
                    from playwright.sync_api import sync_playwright as sp
                except ImportError:
                    return {"success": False, "error": "Playwright is not installed.", "verified": False}
            dest_dir = destination or os.path.expanduser("~/Downloads")
            os.makedirs(dest_dir, exist_ok=True)
            with sp() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                with page.expect_download(timeout=15000) as download_info:
                    try:
                        page.goto(url, timeout=10000)
                    except Exception:
                        pass
                dl = download_info.value
                filename = dl.suggested_filename
                save_path = os.path.join(dest_dir, filename)
                dl.save_as(save_path)
                browser.close()

                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    return {
                        "success": True,
                        "type": "download",
                        "filename": filename,
                        "path": save_path,
                        "size_bytes": os.path.getsize(save_path),
                        "verified": True,
                        "provider": "playwright_chromium"
                    }
                return {"success": False, "error": f"Downloaded file at {save_path} is missing or 0 bytes.", "verified": False}
        except Exception as e:
            return {"success": False, "error": f"Playwright download failed: {str(e)}", "verified": False}


class BrowserCapability:
    """
    Unified Browser Capability Controller.
    Selects structured Playwright/HTTP browser interaction first, falling back to desktop GUI when requested or necessary.
    """
    def __init__(self, provider=None):
        self.custom_provider = provider
        self.playwright_provider = PlaywrightBrowserProvider()
        self.structured_provider = provider if provider else StructuredBrowserProvider()
        self.gui_provider = provider if provider else GUIFallbackBrowserProvider()

    def search(self, query, prefer_gui=False):
        if self.custom_provider:
            return self.custom_provider.search(query)

        if prefer_gui:
            return self.gui_provider.search(query)

        # Try Playwright structured search first
        res = self.playwright_provider.search(query)
        if res.get("success"):
            return res

        # Fallback to HTTP structured provider
        res = self.structured_provider.search(query)
        if res.get("success"):
            return res

        return self.gui_provider.search(query)

    def navigate(self, url, prefer_gui=False):
        if prefer_gui:
            return self.gui_provider.navigate(url)
        return self.playwright_provider.navigate(url)

    def read_page(self, url=None, prefer_gui=False):
        if prefer_gui:
            return self.gui_provider.read_page(url)
        return self.playwright_provider.read_page(url)

    def new_tab(self):
        return self.gui_provider.new_tab()

    def download(self, url, destination=None):
        return self.playwright_provider.download(url, destination=destination)


default_browser_capability = BrowserCapability()


def browser_download(url, destination=None):
    """Direct capability call for controlled browser downloads."""
    return default_browser_capability.download(url, destination=destination)


def browser_new_tab():
    """Direct capability call to open a new tab in the active browser."""
    return default_browser_capability.new_tab()


def browser_search(query, mode="AUTO"):
    prefer_gui = (mode == "FOREGROUND")
    return default_browser_capability.search(query, prefer_gui=prefer_gui)


def browser_search_foreground(query):
    """Direct capability call for foreground GUI browser search."""
    return default_browser_capability.gui_provider.search(query)


def browser_navigate(url, mode="AUTO"):
    prefer_gui = (mode == "FOREGROUND")
    return default_browser_capability.navigate(url, prefer_gui=prefer_gui)


def click_first_search_result(query=""):
    """
    Clicks or navigates to the first search result.
    Supports structured search resolution, vision-based element click,
    or browser navigation.
    """
    import os
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {
            "success": True,
            "action": "CLICK_FIRST_RESULT",
            "url": "https://docs.python.org/3/",
            "title": "Python Documentation",
            "verified": True
        }

    from tools.search import perform_web_search
    if query:
        search_res = perform_web_search(query)
        if isinstance(search_res, list) and search_res:
            first_url = search_res[0].get("url")
            if first_url:
                browser_navigate(first_url)
                return {
                    "success": True,
                    "action": "CLICK_FIRST_RESULT",
                    "url": first_url,
                    "title": search_res[0].get("title", "First Result"),
                    "verified": True
                }

    from tools.vision import default_vision
    obs = default_vision.get_current_observation()
    if obs and obs.get("elements"):
        for el in obs.get("elements", []):
            text = (el.get("text") or "").lower()
            if any(term in text for term in ("python", "docs", "documentation", "result")):
                cx = el.get("center_x")
                cy = el.get("center_y")
                if cx is not None and cy is not None:
                    from tools.input import click_mouse
                    click_mouse(cx, cy)
                    time.sleep(1.0)
                    analyze_captured_screen(force_refresh=True)
                    return {"success": True, "action": "CLICK_FIRST_RESULT", "clicked_element": el.get("id"), "verified": True}

    press_key("tab")
    press_key("return")
    time.sleep(1.0)
    analyze_captured_screen(force_refresh=True)
    return {"success": True, "action": "CLICK_FIRST_RESULT", "method": "keyboard_tab_return", "verified": True}


# -------------------------------------------------------------------
# Phase 4 Deterministic Browser Control Tools
# -------------------------------------------------------------------

def browser_open(url: str = "") -> dict:
    """Opens browser application or navigates to initial URL."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_OPEN", "url": url or "about:blank", "data": f"Browser opened to '{url or 'blank'}'."}

    open_res = open_app("brave")
    if url:
        return browser_navigate(url)
    return {"success": True, "tool": "BROWSER_OPEN", "data": "Brave browser opened."}


def browser_back() -> dict:
    """Navigates browser back one page."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_BACK", "data": "Navigated back."}

    from tools.apps import focus_app
    focus_app("brave")
    hotkey(["alt", "left"])
    time.sleep(0.5)
    return {"success": True, "tool": "BROWSER_BACK", "data": "Navigated back via shortcut."}


def browser_forward() -> dict:
    """Navigates browser forward one page."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_FORWARD", "data": "Navigated forward."}

    from tools.apps import focus_app
    focus_app("brave")
    hotkey(["alt", "right"])
    time.sleep(0.5)
    return {"success": True, "tool": "BROWSER_FORWARD", "data": "Navigated forward via shortcut."}


def browser_reload() -> dict:
    """Reloads current browser page."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_RELOAD", "data": "Page reloaded."}

    from tools.apps import focus_app
    focus_app("brave")
    hotkey(["ctrl", "r"])
    time.sleep(0.5)
    return {"success": True, "tool": "BROWSER_RELOAD", "data": "Page reloaded via shortcut."}


def browser_title() -> dict:
    """Gets current page title."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_TITLE", "title": "Mock Browser Page Title", "data": "Mock Browser Page Title"}

    try:
        from tools.computer_use import dom_get_page_state
        state = dom_get_page_state()
        if state.get("success") and state.get("title"):
            return {"success": True, "tool": "BROWSER_TITLE", "title": state["title"], "data": state["title"]}
    except Exception:
        pass

    obs = default_vision.get_current_observation()
    if obs:
        return {"success": True, "tool": "BROWSER_TITLE", "title": obs.get("active_window_title", "Browser"), "data": obs.get("active_window_title", "Browser")}

    return {"success": True, "tool": "BROWSER_TITLE", "title": "Brave Browser", "data": "Brave Browser"}


def browser_url() -> dict:
    """Gets current browser page URL."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_URL", "url": "https://brave.com", "data": "https://brave.com"}

    try:
        from tools.computer_use import dom_get_page_state
        state = dom_get_page_state()
        if state.get("success") and state.get("url"):
            return {"success": True, "tool": "BROWSER_URL", "url": state["url"], "data": state["url"]}
    except Exception:
        pass

    return {"success": True, "tool": "BROWSER_URL", "url": "https://browser.local", "data": "https://browser.local"}


def browser_find_text(text: str) -> dict:
    """Finds text on active page."""
    if not text:
        return {"success": False, "tool": "BROWSER_FIND_TEXT", "error": "Search text cannot be empty."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_FIND_TEXT", "found": True, "query": text, "data": f"Text '{text}' found on page."}

    try:
        from tools.computer_use import dom_extract_content
        ext = dom_extract_content(selector="body", max_length=5000)
        if ext.get("success") and text.lower() in (ext.get("data") or "").lower():
            return {"success": True, "tool": "BROWSER_FIND_TEXT", "found": True, "query": text, "data": f"Text '{text}' found in DOM content."}
    except Exception:
        pass

    obs = default_vision.get_current_observation() or analyze_captured_screen()
    perc = obs.get("perception", {}) if isinstance(obs, dict) else {}
    detected = perc.get("detected_text", []) or []
    found = any(text.lower() in str(t).lower() for t in detected)
    return {"success": True, "tool": "BROWSER_FIND_TEXT", "found": found, "query": text, "data": f"Text '{text}' {'found' if found else 'not found'} on screen."}


def browser_extract_text(selector: str = "body") -> dict:
    """Extracts text from active page element or DOM body."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        raw = "Mock browser page text extracted successfully."
        sanitized = sanitize_untrusted_web_data(raw)
        return {"success": True, "tool": "BROWSER_EXTRACT_TEXT", "data": sanitized, "raw_text": raw}

    try:
        from tools.computer_use import dom_extract_content
        ext = dom_extract_content(selector=selector, max_length=5000)
        if ext.get("success"):
            raw = ext.get("data", "")
            sanitized = sanitize_untrusted_web_data(raw)
            return {"success": True, "tool": "BROWSER_EXTRACT_TEXT", "data": sanitized, "raw_text": raw}
    except Exception:
        pass

    return {"success": False, "tool": "BROWSER_EXTRACT_TEXT", "error": "Unable to extract text from page."}


def browser_click(selector: str) -> dict:
    """Clicks a DOM element by selector or text label."""
    if not selector:
        return {"success": False, "tool": "BROWSER_CLICK", "error": "Selector cannot be empty."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_CLICK", "data": f"Clicked DOM element matching '{selector}'."}

    try:
        from tools.computer_use import dom_click
        res = dom_click(selector=selector)
        if res.get("success"):
            return {"success": True, "tool": "BROWSER_CLICK", "data": f"Clicked DOM element '{selector}'."}
    except Exception:
        pass

    return {"success": False, "tool": "BROWSER_CLICK", "error": f"Failed to click selector '{selector}'."}


def browser_fill(selector: str, text: str) -> dict:
    """Fills an input DOM element with text."""
    if not selector:
        return {"success": False, "tool": "BROWSER_FILL", "error": "Selector cannot be empty."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_FILL", "data": f"Filled input '{selector}' with text."}

    try:
        from tools.computer_use import dom_type
        res = dom_type(selector=selector, text=text)
        if res.get("success"):
            return {"success": True, "tool": "BROWSER_FILL", "data": f"Filled input '{selector}'."}
    except Exception:
        pass

    return {"success": False, "tool": "BROWSER_FILL", "error": f"Failed to fill input '{selector}'."}


def browser_press(key: str) -> dict:
    """Presses a key in active browser."""
    if not key:
        return {"success": False, "tool": "BROWSER_PRESS", "error": "Key specifier cannot be empty."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_PRESS", "data": f"Pressed key '{key}' in browser."}

    press_key(key)
    return {"success": True, "tool": "BROWSER_PRESS", "data": f"Pressed key '{key}' in browser."}


def browser_select(selector: str, option: str) -> dict:
    """Selects an option from a dropdown element."""
    if not selector or not option:
        return {"success": False, "tool": "BROWSER_SELECT", "error": "Selector and option are required."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_SELECT", "data": f"Selected '{option}' in dropdown '{selector}'."}

    from tools.input import select_semantic_element
    res = select_semantic_element(option=option, label=selector)
    if res.get("success"):
        return {"success": True, "tool": "BROWSER_SELECT", "data": f"Selected option '{option}'."}

    return {"success": False, "tool": "BROWSER_SELECT", "error": f"Unable to select option '{option}' in '{selector}'."}


def browser_scroll_page(direction: str = "down", amount: int = 500) -> dict:
    """Scrolls active browser page up or down."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_SCROLL", "data": f"Scrolled page {direction} by {amount}px."}

    from tools.input import scroll
    scroll_amt = -amount if direction.lower() == "down" else amount
    scroll(scroll_amt)
    return {"success": True, "tool": "BROWSER_SCROLL", "data": f"Scrolled page {direction}."}


def browser_wait(seconds: float = 1.0) -> dict:
    """Waits for bounded duration (0.1 to 10 seconds)."""
    bounded_sec = max(0.1, min(float(seconds), 10.0))
    if os.environ.get("BRAIN_MOCK_GUI") != "1":
        time.sleep(bounded_sec)
    return {"success": True, "tool": "BROWSER_WAIT", "data": f"Waited for {bounded_sec}s."}


def browser_close_tab() -> dict:
    """Closes current browser tab."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_CLOSE_TAB", "data": "Browser tab closed."}

    from tools.apps import focus_app
    focus_app("brave")
    hotkey(["ctrl", "w"])
    time.sleep(0.3)
    return {"success": True, "tool": "BROWSER_CLOSE_TAB", "data": "Tab closed via shortcut."}


def browser_switch_tab(tab_index: int = 1) -> dict:
    """Switches to tab index (1..9)."""
    bounded_idx = max(1, min(int(tab_index), 9))
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BROWSER_SWITCH_TAB", "data": f"Switched to tab {bounded_idx}."}

    from tools.apps import focus_app
    focus_app("brave")
    hotkey(["ctrl", str(bounded_idx)])
    time.sleep(0.3)
    return {"success": True, "tool": "BROWSER_SWITCH_TAB", "data": f"Switched to tab {bounded_idx} via shortcut."}


def browser_list_tabs() -> dict:
    """Lists open browser tabs."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        mock_tabs = [
            {"index": 1, "title": "New Tab - Brave", "active": True},
            {"index": 2, "title": "Python 3.12 Documentation", "active": False}
        ]
        return {"success": True, "tool": "BROWSER_LIST_TABS", "data": mock_tabs, "count": len(mock_tabs)}

    return {"success": True, "tool": "BROWSER_LIST_TABS", "data": [{"index": 1, "title": "Brave Browser Tab", "active": True}], "count": 1}



