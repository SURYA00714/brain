import requests
from html.parser import HTMLParser
from html import unescape
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

    # Try mature duckduckgo_search library first
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(clean_query, max_results=max_results * 2))
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
    for idx, item in enumerate(results, 1):
        formatted_output.append(
            f"{idx}. {item.get('title', 'No title')}\n   Snippet: {item.get('snippet', 'No snippet')}\n   URL: {item.get('url', '')}"
        )

    return "\n\n".join(formatted_output)

