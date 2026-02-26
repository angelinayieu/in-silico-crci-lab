#!/usr/bin/env python3
"""
Web Scraping Test Script for Paper URLs

Takes a list of paper URLs and tests whether content can be extracted.
Reports success/failure for each URL with diagnostic info.

Usage:
    python scripts/test_web_scraping.py URL1 URL2 URL3 ...
    # or
    python scripts/test_web_scraping.py --file urls.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

# Use curl-cffi to bypass TLS fingerprinting (PMC, etc.)
try:
    from curl_cffi import requests
    USING_CURL_CFFI = True
except ImportError:
    import requests
    USING_CURL_CFFI = False

from bs4 import BeautifulSoup

# User agent to avoid bot blocks - must closely mimic real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

TIMEOUT = 30  # seconds


@dataclass
class ExtractionResult:
    """Result of attempting to extract content from a URL."""

    url: str
    success: bool
    status_code: int | None = None
    error: str | None = None
    
    # Extracted fields
    doi: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    journal: str | None = None
    year: str | None = None
    fulltext_link: str | None = None
    pdf_link: str | None = None
    
    # Diagnostics
    source_type: str | None = None  # pubmed, pmc, sciencedirect, etc.
    content_length: int = 0
    has_paywall: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "success": self.success,
            "status_code": self.status_code,
            "error": self.error,
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "journal": self.journal,
            "year": self.year,
            "fulltext_link": self.fulltext_link,
            "pdf_link": self.pdf_link,
            "source_type": self.source_type,
            "content_length": self.content_length,
            "has_paywall": self.has_paywall,
            "warnings": self.warnings,
        }


def detect_source_type(url: str) -> str:
    """Detect the source type from URL."""
    domain = urlparse(url).netloc.lower()
    
    if "pubmed.ncbi" in domain or "ncbi.nlm.nih.gov/pubmed" in url.lower():
        return "pubmed"
    elif "pmc.ncbi.nlm.nih.gov" in domain or "ncbi.nlm.nih.gov/pmc" in url.lower():
        return "pmc"
    elif "sciencedirect" in domain:
        return "sciencedirect"
    elif "springer" in domain or "springerlink" in domain or "link.springer" in domain:
        return "springer"
    elif "wiley" in domain or "onlinelibrary.wiley" in domain:
        return "wiley"
    elif "nature.com" in domain:
        return "nature"
    elif "tandfonline" in domain:
        return "tandfonline"
    elif "frontiersin.org" in domain:
        return "frontiers"
    elif "mdpi.com" in domain:
        return "mdpi"
    elif "plos" in domain:
        return "plos"
    elif "biorxiv" in domain:
        return "biorxiv"
    elif "arxiv" in domain:
        return "arxiv"
    elif "doi.org" in domain:
        return "doi_redirect"
    elif "oup.com" in domain or "academic.oup" in domain:
        return "oxford"
    elif "sage" in domain:
        return "sage"
    elif "jco.ascopubs" in domain or "ascopubs.org" in domain:
        return "asco"
    elif "cell.com" in domain:
        return "cell"
    else:
        return "unknown"


def extract_doi(soup: BeautifulSoup, url: str) -> str | None:
    """Extract DOI from page."""
    # Meta tags
    for attr in ["citation_doi", "DC.identifier", "dc.identifier", "DOI"]:
        meta = soup.find("meta", attrs={"name": attr})
        if meta and meta.get("content"):
            doi = meta["content"]
            if doi.startswith("doi:"):
                doi = doi[4:]
            if doi.startswith("10."):
                return doi
    
    # Schema.org
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                doi = data.get("doi") or data.get("@id")
                if doi and "10." in str(doi):
                    match = re.search(r'10\.\d{4,}/[^\s"<>]+', str(doi))
                    if match:
                        return match.group(0).rstrip(".,;")
        except (json.JSONDecodeError, TypeError):
            continue
    
    # Text patterns
    doi_pattern = r'10\.\d{4,9}/[^\s"<>]+'
    
    # Look in URL
    match = re.search(doi_pattern, url)
    if match:
        return match.group(0).rstrip(".,;")
    
    # Look in page content
    text = soup.get_text()
    match = re.search(doi_pattern, text[:5000])  # First 5000 chars
    if match:
        return match.group(0).rstrip(".,;")
    
    return None


def extract_title(soup: BeautifulSoup) -> str | None:
    """Extract paper title from page."""
    # Meta tags
    for attr in ["citation_title", "DC.title", "dc.title", "og:title"]:
        meta = soup.find("meta", attrs={"name": attr}) or soup.find("meta", attrs={"property": attr})
        if meta and meta.get("content"):
            return meta["content"].strip()
    
    # H1 tags with article-like classes
    for h1 in soup.find_all("h1"):
        classes = h1.get("class", [])
        if any(c in str(classes).lower() for c in ["title", "article", "heading", "headline"]):
            text = h1.get_text(strip=True)
            if len(text) > 10:  # Reasonable title length
                return text
    
    # First non-empty h1
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if len(text) > 10:
            return text
    
    # Fallback to page title
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    
    return None


def extract_authors(soup: BeautifulSoup) -> list[str]:
    """Extract author names from page."""
    authors = []
    
    # Meta tags
    for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
        if meta.get("content"):
            authors.append(meta["content"].strip())
    
    if authors:
        return authors
    
    # DC.creator
    for meta in soup.find_all("meta", attrs={"name": ["DC.creator", "dc.creator"]}):
        if meta.get("content"):
            authors.append(meta["content"].strip())
    
    if authors:
        return authors
    
    # Schema.org
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                author_data = data.get("author", [])
                if isinstance(author_data, list):
                    for a in author_data:
                        if isinstance(a, dict) and a.get("name"):
                            authors.append(a["name"])
                        elif isinstance(a, str):
                            authors.append(a)
        except (json.JSONDecodeError, TypeError):
            continue
    
    return authors[:20]  # Cap at 20


def extract_abstract(soup: BeautifulSoup) -> str | None:
    """Extract abstract from page."""
    # Meta tags
    for attr in ["citation_abstract", "DC.description", "dc.description", "description", "og:description"]:
        meta = soup.find("meta", attrs={"name": attr}) or soup.find("meta", attrs={"property": attr})
        if meta and meta.get("content"):
            content = meta["content"].strip()
            if len(content) > 100:  # Reasonable abstract length
                return content
    
    # Abstract sections
    for selector in [
        {"class": re.compile(r"abstract", re.I)},
        {"id": re.compile(r"abstract", re.I)},
        {"data-testid": "abstract"},
    ]:
        elem = soup.find(["div", "section", "p"], attrs=selector)
        if elem:
            text = elem.get_text(strip=True)
            if len(text) > 100:
                return text
    
    # Heading + content pattern
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if "abstract" in heading.get_text().lower():
            # Get next sibling or parent's text
            parent = heading.find_parent(["div", "section"])
            if parent:
                text = parent.get_text(strip=True)
                # Remove heading text
                text = text.replace(heading.get_text(strip=True), "", 1).strip()
                if len(text) > 100:
                    return text[:3000]  # Cap length
    
    return None


def extract_journal(soup: BeautifulSoup) -> str | None:
    """Extract journal name from page."""
    for attr in ["citation_journal_title", "DC.source", "dc.source"]:
        meta = soup.find("meta", attrs={"name": attr})
        if meta and meta.get("content"):
            return meta["content"].strip()
    return None


def extract_year(soup: BeautifulSoup) -> str | None:
    """Extract publication year from page."""
    for attr in ["citation_publication_date", "citation_date", "DC.date", "dc.date"]:
        meta = soup.find("meta", attrs={"name": attr})
        if meta and meta.get("content"):
            content = meta["content"]
            match = re.search(r"(19|20)\d{2}", content)
            if match:
                return match.group(0)
    return None


def extract_pdf_link(soup: BeautifulSoup, base_url: str) -> str | None:
    """Extract PDF download link from page."""
    # Meta tag
    meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
    if meta and meta.get("content"):
        return meta["content"]
    
    # Links with PDF in href or text
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text().lower()
        if ".pdf" in href.lower() or "pdf" in text:
            if href.startswith("/"):
                # Relative URL
                parsed = urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{href}"
            elif href.startswith("http"):
                return href
    
    return None


def detect_paywall(soup: BeautifulSoup, text: str) -> bool:
    """Detect if page has a paywall."""
    paywall_indicators = [
        "purchase this article",
        "buy this article",
        "subscribe to read",
        "access for",
        "institutional access",
        "log in to access",
        "sign in to access",
        "rent this article",
        "get access",
        "full text not available",
    ]
    
    text_lower = text.lower()
    for indicator in paywall_indicators:
        if indicator in text_lower:
            return True
    
    # Check for paywall classes/IDs
    paywall_elems = soup.find_all(attrs={"class": re.compile(r"paywall|access-denied|restricted", re.I)})
    if paywall_elems:
        return True
    
    return False


def scrape_url(url: str) -> ExtractionResult:
    """Scrape a single URL and extract paper metadata."""
    result = ExtractionResult(url=url, success=False)
    result.source_type = detect_source_type(url)
    
    try:
        # Handle DOI redirects
        if result.source_type == "doi_redirect":
            result.warnings.append("DOI redirect - following to final URL")
        
        # Use curl_cffi with Chrome impersonation to bypass TLS fingerprinting
        if USING_CURL_CFFI:
            response = requests.get(url, impersonate="chrome", timeout=TIMEOUT, allow_redirects=True)
        else:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        
        result.status_code = response.status_code
        result.content_length = len(response.content)
        
        if response.status_code != 200:
            result.error = f"HTTP {response.status_code}"
            return result
        
        # Update source type after redirect
        if response.url != url:
            result.source_type = detect_source_type(response.url)
            result.warnings.append(f"Redirected to: {response.url}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()
        
        # Extract fields
        result.doi = extract_doi(soup, response.url)
        result.title = extract_title(soup)
        result.authors = extract_authors(soup)
        result.abstract = extract_abstract(soup)
        result.journal = extract_journal(soup)
        result.year = extract_year(soup)
        result.pdf_link = extract_pdf_link(soup, response.url)
        result.has_paywall = detect_paywall(soup, page_text)
        
        # Determine success
        has_essential = bool(result.title or result.doi)
        has_content = bool(result.abstract) or result.content_length > 10000
        
        if has_essential:
            result.success = True
            if not result.doi:
                result.warnings.append("DOI not found")
            if not result.abstract:
                result.warnings.append("Abstract not found")
            if not result.authors:
                result.warnings.append("Authors not found")
            if result.has_paywall:
                result.warnings.append("Paywall detected - full text may not be accessible")
        else:
            result.error = "Could not extract title or DOI"
        
    except requests.Timeout:
        result.error = "Request timed out"
    except requests.ConnectionError as e:
        result.error = f"Connection error: {e}"
    except Exception as e:
        result.error = f"Unexpected error: {type(e).__name__}: {e}"
    
    return result


def print_result(result: ExtractionResult, verbose: bool = False) -> None:
    """Print extraction result in readable format."""
    status = "✓" if result.success else "✗"
    print(f"\n{status} {result.url}")
    print(f"  Source: {result.source_type or 'unknown'}")
    
    if result.error:
        print(f"  ERROR: {result.error}")
        return
    
    print(f"  Status: HTTP {result.status_code}")
    
    if result.title:
        title_short = result.title[:80] + "..." if len(result.title) > 80 else result.title
        print(f"  Title: {title_short}")
    
    if result.doi:
        print(f"  DOI: {result.doi}")
    
    if result.authors:
        authors_str = ", ".join(result.authors[:3])
        if len(result.authors) > 3:
            authors_str += f" + {len(result.authors) - 3} more"
        print(f"  Authors: {authors_str}")
    
    if result.journal:
        print(f"  Journal: {result.journal}")
    
    if result.year:
        print(f"  Year: {result.year}")
    
    if result.abstract and verbose:
        abstract_short = result.abstract[:200] + "..." if len(result.abstract) > 200 else result.abstract
        print(f"  Abstract: {abstract_short}")
    elif result.abstract:
        print(f"  Abstract: {len(result.abstract)} chars")
    
    if result.pdf_link:
        print(f"  PDF: {result.pdf_link}")
    
    if result.has_paywall:
        print("  ⚠ PAYWALL DETECTED")
    
    if result.warnings:
        for w in result.warnings:
            print(f"  ⚠ {w}")


def main():
    parser = argparse.ArgumentParser(description="Test web scraping on paper URLs")
    parser.add_argument("urls", nargs="*", help="URLs to scrape")
    parser.add_argument("--file", "-f", help="File containing URLs (one per line)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full abstracts")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Delay between requests (seconds)")
    
    args = parser.parse_args()
    
    urls = list(args.urls)
    
    if args.file:
        with open(args.file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    
    if not urls:
        print("No URLs provided. Usage:")
        print("  python scripts/test_web_scraping.py URL1 URL2 ...")
        print("  python scripts/test_web_scraping.py --file urls.txt")
        sys.exit(1)
    
    print(f"Testing {len(urls)} URLs...\n")
    
    results = []
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(args.delay)
        
        result = scrape_url(url)
        results.append(result)
        
        if not args.json:
            print_result(result, verbose=args.verbose)
    
    # Summary
    success_count = sum(1 for r in results if r.success)
    paywall_count = sum(1 for r in results if r.has_paywall)
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: {success_count}/{len(results)} successful")
    if paywall_count:
        print(f"         {paywall_count} with paywall")
    
    by_source = {}
    for r in results:
        src = r.source_type or "unknown"
        if src not in by_source:
            by_source[src] = {"total": 0, "success": 0}
        by_source[src]["total"] += 1
        if r.success:
            by_source[src]["success"] += 1
    
    print("\nBy source:")
    for src, counts in sorted(by_source.items()):
        print(f"  {src}: {counts['success']}/{counts['total']}")
    
    if args.json:
        print("\n" + json.dumps([r.to_dict() for r in results], indent=2))


if __name__ == "__main__":
    main()
