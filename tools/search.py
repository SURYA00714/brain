import ipaddress
import re
import requests
from html.parser import HTMLParser
from html import unescape
from typing import Tuple, Optional, Any, Dict, List
from urllib.parse import urlparse, parse_qs, unquote


def clean_url(raw_url):
    """
    Sanitizes search result URLs:
    - Rejects DuckDuckGo advertisement/tracking links (e.g. duckduckgo.com/y.js, ad_domain=).
    - Decodes DuckDuckGo redirect URLs (/l/?uddg=...) into clean destination URLs.
    - Returns clean destination URL or None if invalid/ad link.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    url = raw_url.strip()
    if url.startswith("//"):
        url = "https:" + url

    # Reject advertisement or tracking redirect URLs
    if "duckduckgo.com/y.js" in url or "ad_domain=" in url or "ad_provider=" in url:
        return None

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Decode DuckDuckGo redirect parameter (uddg=)
    if "uddg" in query_params and query_params["uddg"]:
        target_url = unquote(query_params["uddg"][0])
        # Verify decoded target URL is not an ad link
        if "ad_domain=" in target_url or "duckduckgo.com/y.js" in target_url or "ad_provider=" in target_url:
            return None
        if target_url.startswith(("http://", "https://")):
            return target_url
        return None

    # Direct valid HTTP/HTTPS URL
    if parsed.scheme in ("http", "https") and "duckduckgo.com" not in parsed.netloc:
        return url

    return None


class DDGHTMLParser(HTMLParser):
    """Parses titles, snippets, and clean destination links from DuckDuckGo HTML search results."""
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_snippet = False
        self.current_title = ""
        self.current_snippet = ""
        self.current_link = ""
        self.results = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in cls:
            self.in_title = True
            self.current_title = ""
            raw_href = attrs_dict.get("href", "")
            self.current_link = clean_url(raw_href)
        elif tag == "a" and "result__snippet" in cls:
            self.in_snippet = True
            self.current_snippet = ""

    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            self.in_title = False
        elif tag == "a" and self.in_snippet:
            self.in_snippet = False
            # Only record result if it has a clean, non-ad destination URL
            if self.current_link and (self.current_title or self.current_snippet):
                self.results.append({
                    "title": unescape(self.current_title).strip(),
                    "snippet": unescape(self.current_snippet).strip(),
                    "link": self.current_link
                })

    def handle_data(self, data):
        if self.in_title:
            self.current_title += data
        if self.in_snippet:
            self.current_snippet += data


def perform_web_search_structured(query, max_results=3):
    """
    Performs a web search using duckduckgo_search library with fallback to HTML scraper.
    Returns normalized dictionary contract:
    {
      "success": bool,
      "query": str,
      "results": [{"title": str, "url": str, "snippet": str}],
      "provider": str,
      "status": str
    }
    """
    clean_query = query.strip() if query else ""
    if not clean_query:
        return {
            "success": False,
            "query": "",
            "results": [],
            "provider": "duckduckgo",
            "status": "ERROR_EMPTY_QUERY"
        }

    # Try mature duckduckgo_search / ddgs library first
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                from ddgs import DDGS
            except Exception:
                try:
                    from duckduckgo_search import DDGS
                except Exception:
                    DDGS = None
            if DDGS is not None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    with DDGS() as ddgs:
                        raw_results = list(ddgs.text(clean_query, max_results=max_results * 2))
            else:
                raw_results = []
            clean_results = []
            for r in raw_results:
                link = clean_url(r.get("href") or r.get("link") or "")
                if link and (r.get("title") or r.get("body")):
                    clean_results.append({
                        "title": r.get("title", "").strip(),
                        "url": link,
                        "snippet": (r.get("body") or r.get("snippet") or "").strip()
                    })
                if len(clean_results) >= max_results:
                    break

            if clean_results:
                return {
                    "success": True,
                    "query": clean_query,
                    "results": clean_results,
                    "provider": "duckduckgo_ddgs",
                    "status": "COMPLETED"
                }
    except Exception:
        pass  # Fall back to HTML parser below

    # Fallback to internal DDGHTMLParser
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(url, data={"q": clean_query}, headers=headers, timeout=10)
        response.raise_for_status()

        parser = DDGHTMLParser()
        parser.feed(response.text)

        clean_results = []
        for item in parser.results:
            if len(clean_results) >= max_results:
                break
            link = item.get("link")
            if link:
                clean_results.append({
                    "title": item.get("title", ""),
                    "url": link,
                    "snippet": item.get("snippet", "")
                })

        return {
            "success": len(clean_results) > 0,
            "query": clean_query,
            "results": clean_results,
            "provider": "duckduckgo_html",
            "status": "COMPLETED" if clean_results else "NO_RESULTS"
        }
    except Exception as e:
        return {
            "success": False,
            "query": clean_query,
            "results": [],
            "provider": "duckduckgo_html",
            "status": f"ERROR: {str(e)}"
        }


def perform_web_search(query, max_results=3):
    """
    Performs a web search for the given query using DuckDuckGo HTML endpoint.
    Returns a formatted string containing titles, snippets, and clean destination URLs.
    """
    struct_res = perform_web_search_structured(query, max_results=max_results)
    if not struct_res.get("success"):
        return f"No web search results found for '{query}'."

    results = struct_res.get("results", [])
    if not results:
        return f"No valid web search results found for '{query}'."

    formatted_output = [f"Search results for '{query}':"]
    for idx, r in enumerate(results[:max_results], 1):
        title = r.get("title", "")
        snip = r.get("snippet", "")
        url = r.get("url", "")
        formatted_output.append(f"{idx}. {title}\n   {snip}\n   URL: {url}")
    return "\n\n".join(formatted_output)


def is_safe_web_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validates that a URL is safe to fetch (HTTP/HTTPS, no private IP/SSRF)."""
    if not url or not isinstance(url, str):
        return False, "Error: URL parameter cannot be empty."
    url_clean = url.strip()
    if not url_clean.startswith(("http://", "https://")):
        return False, "Error: Only HTTP and HTTPS URLs are allowed."
    try:
        parsed = urlparse(url_clean)
        hostname = parsed.hostname
        if not hostname:
            return False, "Error: Invalid URL hostname."

        # Check against local / private IPs
        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False, "Security Block: Access to localhost or internal network is prohibited."

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return False, f"Security Block: Access to private IP '{hostname}' is prohibited."
        except ValueError:
            pass  # Domain name, not raw IP literal

        return True, None
    except Exception as e:
        return False, f"Error validating URL: {str(e)}"


def read_web_page(url: str, max_chars: int = 8000) -> dict:
    """
    Fetches an allowed public web page, strips scripts/markup,
    and extracts clean readable text content.
    Returns:
    {
        "success": bool,
        "url": str,
        "title": str,
        "content": str,
        "data": str,
        "status": str
    }
    """
    safe, err = is_safe_web_url(url)
    if not safe:
        return {"success": False, "url": url, "error": err, "status": "SECURITY_BLOCK", "data": err}

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    try:
        response = requests.get(url.strip(), headers=headers, timeout=8, stream=True)
        response.raise_for_status()

        # Guard against non-text content types
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and not any(t in content_type for t in ("text/html", "text/plain", "application/xhtml+xml", "text/")):
            err_msg = f"Unsupported content type: {content_type}"
            return {"success": False, "url": url, "error": err_msg, "status": "UNSUPPORTED_TYPE", "data": err_msg}

        raw_html = ""
        for chunk in response.iter_content(chunk_size=32768, decode_unicode=True):
            if chunk:
                raw_html += chunk
            if len(raw_html) > 262144:
                break

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw_html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
                tag.decompose()
            page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
            text = soup.get_text(separator="\n")
        except Exception:
            page_title = ""
            text = re.sub(r"<script[^>]*>.*?</script>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)
        if len(cleaned_text) > max_chars:
            cleaned_text = cleaned_text[:max_chars] + f"\n... [Truncated at {max_chars} characters]"

        summary_display = f"Title: {page_title}\nURL: {url}\n\nContent:\n{cleaned_text}" if page_title else f"URL: {url}\n\nContent:\n{cleaned_text}"

        return {
            "success": True,
            "url": url,
            "title": page_title,
            "content": cleaned_text,
            "data": summary_display,
            "status": "COMPLETED"
        }
    except requests.exceptions.Timeout:
        err_msg = "Request timed out after 8 seconds."
        return {"success": False, "url": url, "error": err_msg, "status": "TIMEOUT", "data": err_msg}
    except requests.exceptions.RequestException as e:
        err_msg = f"Failed to fetch webpage: {str(e)}"
        return {"success": False, "url": url, "error": err_msg, "status": "FETCH_ERROR", "data": err_msg}
    except Exception as e:
        err_msg = f"Error parsing webpage: {str(e)}"
        return {"success": False, "url": url, "error": err_msg, "status": "PARSE_ERROR", "data": err_msg}


def research_topic(query: str, max_results: int = 3, deep: bool = True) -> dict:
    """
    Intelligent web research workflow:
    SEARCH -> COLLECT -> DEEP FETCH -> FILTER -> SYNTHESIZE
    Returns structured research findings, extracted page facts, and grounded summary.
    """
    struct_res = perform_web_search_structured(query, max_results=max_results * 2)
    if not struct_res.get("success") or not struct_res.get("results"):
        return {
            "success": False,
            "query": query,
            "findings": [],
            "sources": [],
            "retrieved_summary": f"Could not find web search information for '{query}'."
        }

    raw_results = struct_res.get("results", [])
    findings = []
    sources = []
    seen_texts = set()

    for item in raw_results:
        snippet = item.get("snippet", "").strip()
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()

        if snippet and snippet not in seen_texts:
            seen_texts.add(snippet)
            findings.append(f"{title}: {snippet}")
            if url and url not in sources:
                sources.append(url)
        if len(findings) >= max_results:
            break

    # Deep Research: Fetch top source pages to extract primary ground truth facts
    deep_extracts = []
    if deep and sources:
        query_words = [w.lower() for w in re.findall(r"\b\w{3,}\b", query) if w.lower() not in ("what", "when", "where", "which", "about", "latest", "recent", "search")]
        for src_url in sources[:2]:
            page_data = read_web_page(src_url, max_chars=3000)
            if page_data.get("success") and page_data.get("content"):
                p_text = page_data["content"]
                p_paragraphs = [p.strip() for p in p_text.split("\n\n") if len(p.strip()) > 40]
                matched_paragraphs = []
                for p in p_paragraphs:
                    p_low = p.lower()
                    if any(w in p_low for w in query_words):
                        matched_paragraphs.append(p[:300].strip())
                        if len(matched_paragraphs) >= 2:
                            break
                for mp in matched_paragraphs:
                    deep_extracts.append(f"Source ({src_url}): {mp}")

    all_evidence = findings + deep_extracts
    summary_text = "\n".join(f"- {f}" for f in (all_evidence[:5] if all_evidence else findings))

    return {
        "success": True,
        "query": query,
        "findings": all_evidence if all_evidence else findings,
        "sources": sources,
        "retrieved_summary": summary_text,
        "deep_extracts": deep_extracts
    }


