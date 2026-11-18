"""
Universal Website Search & Input Detection Engine for Brain.
Implements universal DOM element inspection, multi-signal confidence ranking,
safe form/button submission, and post-execution verification across unknown websites.
"""

import re
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass
class CandidateInputElement:
    selector: str
    tag_name: str = "input"
    input_type: str = "text"
    name: str = ""
    element_id: str = ""
    placeholder: str = ""
    aria_label: str = ""
    role: str = ""
    title: str = ""
    form_action: str = ""
    form_role: str = ""
    form_id: str = ""
    has_search_button: bool = False
    search_button_selector: str = ""
    is_visible: bool = True
    is_enabled: bool = True
    score: float = 0.0
    score_reasons: List[str] = field(default_factory=list)


class BrowserPageInspector:
    """
    Inspects HTML or live DOM trees to identify interactive input candidates,
    associated forms, and search submission buttons while filtering out sensitive
    or non-search fields.
    """

    # Strictly excluded sensitive or credential keywords
    EXCLUDED_KEYWORDS = {
        "password", "pass", "pwd", "secret", "token", "otp", "pin",
        "cvv", "cvc", "creditcard", "cardnumber", "card_number", "billing",
        "ssn", "socialsecurity", "captcha"
    }

    # Non-search input keywords to heavily penalize
    NON_SEARCH_KEYWORDS = {
        "email", "login", "signin", "signup", "username", "user",
        "phone", "tel", "mobile", "address", "zip", "postal", "city",
        "country", "coupon", "promo", "discount", "voucher",
        "newsletter", "subscribe", "first_name", "last_name", "fname", "lname"
    }

    SEARCH_KEYWORDS = {
        "search", "query", "find", "keyword", "keywords", "kw", "q",
        "searchbox", "search_box", "search-box", "searchform", "search_form",
        "lookup", "explore", "filter", "searchinput", "search_input"
    }

    BUTTON_SEARCH_KEYWORDS = {
        "search", "find", "go", "submit", "lookup", "explore"
    }

    def inspect_html(self, html: str) -> List[CandidateInputElement]:
        """Inspects HTML string to extract candidate search input elements."""
        if not html or not isinstance(html, str):
            return []

        soup = BeautifulSoup(html, "html.parser")
        candidates: List[CandidateInputElement] = []

        # Find all inputs, textareas, and contenteditable elements
        elements = soup.find_all(["input", "textarea"]) + soup.find_all(attrs={"contenteditable": True})

        # Check iframes for nested/fallback HTML content
        for iframe in soup.find_all("iframe"):
            inner_html = iframe.string or ""
            if "<input" in inner_html or "<textarea" in inner_html or "contenteditable" in inner_html:
                iframe_soup = BeautifulSoup(inner_html, "html.parser")
                elements.extend(
                    iframe_soup.find_all(["input", "textarea"]) + iframe_soup.find_all(attrs={"contenteditable": True})
                )

        for el in elements:
            tag = el.name.lower()
            itype = el.get("type", "text").lower() if tag == "input" else tag

            # Filter out obvious non-text input types
            if itype in ("hidden", "checkbox", "radio", "button", "submit", "image", "file", "reset"):
                continue

            # Check disabled / readonly
            is_enabled = not (el.has_attr("disabled") or el.has_attr("readonly"))
            if not is_enabled:
                continue

            # Check style visibility
            style = el.get("style", "").lower()
            if "display: none" in style or "display:none" in style or "visibility: hidden" in style or "visibility:hidden" in style:
                continue

            # Check hidden attribute
            if el.has_attr("hidden"):
                continue

            # Check class names for hidden
            classes = " ".join(el.get("class", [])).lower()
            if "hidden" in classes and "not-hidden" not in classes:
                continue

            name = el.get("name", "")
            el_id = el.get("id", "")
            placeholder = el.get("placeholder", "")
            aria_label = el.get("aria-label", "") or el.get("aria-labelledby", "")
            role = el.get("role", "")
            title = el.get("title", "")

            # Exclude sensitive fields outright
            combined_ident = f"{name} {el_id} {itype} {placeholder} {aria_label} {title}".lower()
            if any(k in combined_ident for k in self.EXCLUDED_KEYWORDS):
                continue

            # Check parent form
            parent_form = el.find_parent("form")
            form_action = parent_form.get("action", "") if parent_form else ""
            form_role = parent_form.get("role", "") if parent_form else ""
            form_id = parent_form.get("id", "") if parent_form else ""

            # Check for nearby or form search buttons
            has_button = False
            button_sel = ""
            if parent_form:
                buttons = parent_form.find_all(["button", "input"])
                for b in buttons:
                    b_type = b.get("type", "").lower()
                    if b.name == "button" or b_type in ("submit", "button"):
                        b_text = b.get_text(strip=True).lower()
                        b_val = b.get("value", "").lower()
                        b_aria = b.get("aria-label", "").lower()
                        b_title = b.get("title", "").lower()
                        b_id = b.get("id", "")
                        b_class = " ".join(b.get("class", []))
                        b_combined = f"{b_text} {b_val} {b_aria} {b_title} {b_id} {b_class}".lower()
                        if any(sk in b_combined for sk in self.BUTTON_SEARCH_KEYWORDS) or b_type == "submit":
                            has_button = True
                            button_sel = f"#{b_id}" if b_id else ("button[type='submit']" if b.name == "button" else "input[type='submit']")
                            break

            # Build stable selector
            if el_id:
                sel = f"#{el_id}"
            elif name:
                sel = f"{tag}[name='{name}']"
            elif role:
                sel = f"{tag}[role='{role}']"
            elif placeholder:
                sel = f"{tag}[placeholder='{placeholder}']"
            else:
                sel = f"{tag}[type='{itype}']"

            candidate = CandidateInputElement(
                selector=sel,
                tag_name=tag,
                input_type=itype,
                name=name,
                element_id=el_id,
                placeholder=placeholder,
                aria_label=aria_label,
                role=role,
                title=title,
                form_action=form_action,
                form_role=form_role,
                form_id=form_id,
                has_search_button=has_button,
                search_button_selector=button_sel,
                is_visible=True,
                is_enabled=is_enabled
            )
            candidates.append(candidate)

        return candidates


class SearchFieldRanker:
    """
    Ranks candidate elements using a multi-signal confidence scoring model.
    Handles disambiguation and identifies when an input is missing or ambiguous.
    """

    def rank_candidates(self, candidates: List[CandidateInputElement]) -> List[CandidateInputElement]:
        """Scores and sorts candidate input elements by likelihood of being the primary search box."""
        for c in candidates:
            score = 0.0
            reasons = []

            # 1. HTML Type Signal
            if c.input_type == "search":
                score += 100.0
                reasons.append("type='search' (+100)")
            elif c.input_type in ("text", "url"):
                score += 10.0
                reasons.append(f"type='{c.input_type}' (+10)")

            # 2. ARIA Role Signal
            if c.role in ("searchbox", "search"):
                score += 90.0
                reasons.append(f"role='{c.role}' (+90)")

            if c.form_role == "search":
                score += 40.0
                reasons.append("form role='search' (+40)")

            # 3. Name & ID Signals
            combined_id_name = f"{c.name} {c.element_id}".lower()
            if any(k in combined_id_name for k in ("search", "query", "find")):
                score += 50.0
                reasons.append("name/id contains search/query/find (+50)")
            elif combined_id_name.strip() in ("q", "k", "kw", "s"):
                score += 45.0
                reasons.append("common query shorthand 'q'/'s' (+45)")

            # 4. Placeholder & Label Signals
            combined_labels = f"{c.placeholder} {c.aria_label} {c.title}".lower()
            if any(k in combined_labels for k in ("search", "find", "query", "explore", "lookup")):
                score += 60.0
                reasons.append("placeholder/aria/title contains search term (+60)")

            # 5. Form Action Signal
            if any(k in c.form_action.lower() for k in ("search", "query", "results", "find")):
                score += 35.0
                reasons.append("form action points to search endpoint (+35)")

            # 6. Search Button Association
            if c.has_search_button:
                score += 30.0
                reasons.append("associated search/submit button detected (+30)")

            # 7. Non-Search Penalties
            combined_text = f"{combined_id_name} {combined_labels}".lower()
            for nsk in BrowserPageInspector.NON_SEARCH_KEYWORDS:
                if nsk in combined_text:
                    score -= 150.0
                    reasons.append(f"non-search keyword '{nsk}' detected (-150)")
                    break

            c.score = max(0.0, score)
            c.score_reasons = reasons

        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates

    def select_best_candidate(self, candidates: List[CandidateInputElement], threshold: float = 30.0) -> Tuple[Optional[CandidateInputElement], str]:
        """
        Selects the top candidate or returns ambiguity/absence status.
        Status: 'SUCCESS', 'INPUT_NOT_FOUND', 'AMBIGUOUS_INPUT'
        """
        ranked = self.rank_candidates(candidates)
        if not ranked or ranked[0].score < threshold:
            return None, "INPUT_NOT_FOUND"

        best = ranked[0]
        # Ambiguity check: if there is a second candidate with a very close high score (>50)
        if len(ranked) > 1:
            second = ranked[1]
            if second.score >= threshold and (best.score - second.score) <= 15.0 and second.score > 50.0:
                # If both have identical search indicators without clear differentiator
                return None, "AMBIGUOUS_INPUT"

        return best, "SUCCESS"


class SearchVerificationEngine:
    """
    Verifies that search input submission produced meaningful page changes,
    URL query parameters, or search result content.
    """

    SEARCH_CONTAINER_SELECTORS = [
        ".search-results", "#search-results", ".results", "#results",
        "[role='feed']", "[role='main']", ".search_results", ".search-content",
        ".search-items", "ul.results", "div.results", ".result-list"
    ]

    def verify(
        self,
        query: str,
        initial_url: str,
        final_url: str,
        initial_content: str,
        final_content: str,
        html: str = ""
    ) -> Tuple[bool, str, str]:
        """
        Verifies whether search was successful.
        Returns: (verified: bool, status: str, evidence: str)
        """
        clean_q = query.strip()
        if not clean_q:
            return False, "SUBMISSION_FAILED", "Empty query provided."

        query_tokens = [w.lower() for w in clean_q.split() if len(w) > 2]
        evidence_points = []

        # 1. URL Analysis
        url_changed = (initial_url != final_url)
        encoded_q_plus = urllib.parse.quote_plus(clean_q).lower()
        encoded_q_perc = urllib.parse.quote(clean_q).lower()
        raw_q_lower = clean_q.lower()

        url_has_query = any(
            t in final_url.lower() for t in (encoded_q_plus, encoded_q_perc, raw_q_lower)
        )
        url_has_search_path = any(
            p in final_url.lower() for p in ("/search", "/results", "?q=", "?query=", "?s=", "?search=")
        )

        if url_has_query:
            evidence_points.append(f"Query terms confirmed in destination URL ({final_url})")
        if url_has_search_path:
            evidence_points.append(f"URL navigated to search endpoint ({final_url})")

        # 2. Page Content & Results Container Analysis
        content_changed = (initial_content != final_content)
        query_in_final = any(t in final_content.lower() for t in query_tokens) if query_tokens else True

        if html:
            soup = BeautifulSoup(html, "html.parser")
            for sel in self.SEARCH_CONTAINER_SELECTORS:
                if soup.select(sel):
                    evidence_points.append(f"Search results container matching '{sel}' detected")
                    break

        if content_changed and query_in_final:
            evidence_points.append("Page content updated with query-relevant text")

        # Decision Matrix
        if url_has_query or (url_has_search_path and (content_changed or query_in_final)):
            return True, "SUCCESS", "; ".join(evidence_points) or "Search query submitted and verified."

        if content_changed and query_in_final:
            return True, "PARTIAL_SUCCESS", "; ".join(evidence_points) or "Page content changed with search terms."

        if url_changed:
            return True, "PARTIAL_SUCCESS", f"Navigation occurred to {final_url}."

        return False, "VERIFICATION_FAILED", "No search result indicators or URL changes observed."


class UniversalSearchExecutor:
    """
    Coordinates browser page inspection, search candidate ranking, execution,
    and verification across arbitrary websites.
    """

    def __init__(self):
        self.inspector = BrowserPageInspector()
        self.ranker = SearchFieldRanker()
        self.verifier = SearchVerificationEngine()

    def execute_search(
        self,
        query: str,
        url: Optional[str] = None,
        html_fixture: Optional[str] = None,
        mock_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Executes universal search across a website or mock fixture.
        Returns standardized execution dictionary.
        """
        import os
        is_mock = mock_mode or os.environ.get("BRAIN_MOCK_GUI") == "1"

        clean_query = (query or "").strip()
        if not clean_query:
            return {
                "success": False,
                "status": "SUBMISSION_FAILED",
                "website": url or "active_page",
                "input_detected": False,
                "input_type": "",
                "query_submitted": "",
                "submission_method": "",
                "verified": False,
                "evidence": "Search query cannot be empty."
            }

        # Determine website domain
        website_domain = ""
        if url:
            parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
            website_domain = parsed.netloc or url
        else:
            website_domain = "active_page"

        # 1. Mock / Fixture Mode
        if is_mock or html_fixture is not None:
            html = html_fixture or """
            <html><body>
                <form action="/search" method="get">
                    <input type="search" name="q" placeholder="Search tutorials">
                    <button type="submit">Search</button>
                </form>
            </body></html>
            """
            candidates = self.inspector.inspect_html(html)
            best_candidate, rank_status = self.ranker.select_best_candidate(candidates)

            if rank_status != "SUCCESS" or not best_candidate:
                return {
                    "success": False,
                    "status": rank_status,
                    "website": website_domain,
                    "input_detected": False,
                    "input_type": "",
                    "query_submitted": clean_query,
                    "submission_method": "",
                    "verified": False,
                    "evidence": f"Detection ended with status: {rank_status}"
                }

            # Verification in mock mode
            sub_method = "button" if best_candidate.has_search_button else "enter_key"
            verified, ver_status, evidence = self.verifier.verify(
                query=clean_query,
                initial_url=url or "https://example.com",
                final_url=f"https://{website_domain}/search?q={urllib.parse.quote_plus(clean_query)}",
                initial_content="Home page",
                final_content=f"Search results for {clean_query}",
                html=html
            )

            return {
                "success": verified,
                "status": ver_status,
                "website": website_domain,
                "input_detected": True,
                "input_type": best_candidate.input_type,
                "selector": best_candidate.selector,
                "query_submitted": clean_query,
                "submission_method": sub_method,
                "verified": verified,
                "evidence": evidence
            }

        # 2. Live Playwright / Browser Mode
        try:
            from tools.computer_use import get_active_browser_page
            from tools.browser import browser_open, browser_navigate

            page = get_active_browser_page()
            if url:
                browser_navigate(url)
                page = get_active_browser_page()

            if not page:
                # Fallback to desktop browser foreground search
                from tools.browser import default_browser_capability
                res = default_browser_capability.search(clean_query, prefer_gui=True)
                return {
                    "success": res.get("success", False),
                    "status": "SUCCESS" if res.get("success") else "SUBMISSION_FAILED",
                    "website": website_domain,
                    "input_detected": True,
                    "input_type": "address_bar",
                    "query_submitted": clean_query,
                    "submission_method": "gui_foreground",
                    "verified": res.get("verified", False),
                    "evidence": res.get("verification_detail", "Desktop browser search executed.")
                }

            initial_url = page.url
            initial_content = page.inner_text("body")
            html = page.content()

            candidates = self.inspector.inspect_html(html)
            best_candidate, rank_status = self.ranker.select_best_candidate(candidates)

            if rank_status != "SUCCESS" or not best_candidate:
                return {
                    "success": False,
                    "status": rank_status,
                    "website": website_domain,
                    "input_detected": False,
                    "input_type": "",
                    "query_submitted": clean_query,
                    "submission_method": "",
                    "verified": False,
                    "evidence": f"Detection failed with status: {rank_status}"
                }

            # Fill input
            sub_method = "enter_key"
            loc = page.locator(best_candidate.selector).first
            loc.fill(clean_query)

            if best_candidate.has_search_button and best_candidate.search_button_selector:
                try:
                    btn = page.locator(best_candidate.search_button_selector).first
                    btn.click(timeout=3000)
                    sub_method = "button"
                except Exception:
                    loc.press("Enter")
                    sub_method = "enter_key"
            else:
                loc.press("Enter")
                sub_method = "enter_key"

            page.wait_for_load_state("domcontentloaded", timeout=5000)

            final_url = page.url
            final_content = page.inner_text("body")
            final_html = page.content()

            verified, ver_status, evidence = self.verifier.verify(
                query=clean_query,
                initial_url=initial_url,
                final_url=final_url,
                initial_content=initial_content,
                final_content=final_content,
                html=final_html
            )

            return {
                "success": verified,
                "status": ver_status,
                "website": website_domain,
                "input_detected": True,
                "input_type": best_candidate.input_type,
                "selector": best_candidate.selector,
                "query_submitted": clean_query,
                "submission_method": sub_method,
                "verified": verified,
                "evidence": evidence
            }

        except Exception as e:
            return {
                "success": False,
                "status": "SUBMISSION_FAILED",
                "website": website_domain,
                "input_detected": False,
                "input_type": "",
                "query_submitted": clean_query,
                "submission_method": "",
                "verified": False,
                "evidence": f"Browser interaction error: {str(e)}"
            }


default_search_executor = UniversalSearchExecutor()
