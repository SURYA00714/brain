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


def perform_web_search(query, max_results=3):
    """
    Performs a web search for the given query using DuckDuckGo HTML endpoint.
    Returns a formatted string containing titles, snippets, and clean destination URLs.
    """
    clean_query = query.strip() if query else ""
    if not clean_query:
        return "Search query cannot be empty."

    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(url, data={"q": clean_query}, headers=headers, timeout=10)
        response.raise_for_status()

        parser = DDGHTMLParser()
        parser.feed(response.text)

        if not parser.results:
            return f"No web search results found for '{clean_query}'."

        formatted_output = [f"Search results for '{clean_query}':"]
        count = 0
        for item in parser.results:
            if count >= max_results:
                break
            title = item.get("title") or "No title"
            snippet = item.get("snippet") or "No snippet"
            link = item.get("link")
            if not link:
                continue

            count += 1
            formatted_output.append(f"{count}. {title}\n   Snippet: {snippet}\n   URL: {link}")

        if count == 0:
            return f"No valid web search results found for '{clean_query}'."

        return "\n\n".join(formatted_output)

    except requests.exceptions.ConnectionError:
        return "Error: Unable to connect to search service. Please check your internet connection."
    except requests.exceptions.Timeout:
        return "Error: Web search request timed out."
    except requests.exceptions.RequestException as e:
        return f"Error executing web search: {str(e)}"
    except Exception as e:
        return f"Unexpected error during web search: {str(e)}"
