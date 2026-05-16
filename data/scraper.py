"""
data/scraper.py
Real competitor price scraper for Indian e-commerce sites.
Scrapes Amazon.in, Flipkart, Myntra, Nykaa, BigBasket.

Usage:
    scraper = CompetitorScraper()
    prices = scraper.scrape_product("ELEC-001")
    all_prices = scraper.scrape_all()
"""

import time
import random
import requests
from datetime import datetime
from typing import Optional
from loguru import logger
from bs4 import BeautifulSoup

from data.catalogue import ALL_PRODUCTS, Product, PRODUCT_MAP


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class CompetitorScraper:
    """
    Scrapes competitor prices from Indian e-commerce sites.
    Includes polite rate limiting and site-specific parsers.
    """

    def __init__(self, delay_range: tuple = (2, 5)):
        self.delay_range = delay_range
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scrape_all(self) -> list[dict]:
        """Scrape all products in the catalogue."""
        all_results = []
        for product in ALL_PRODUCTS:
            results = self.scrape_product(product.id)
            all_results.extend(results)
            time.sleep(random.uniform(*self.delay_range))
        logger.info(f"Scraped {len(all_results)} competitor prices for {len(ALL_PRODUCTS)} products")
        return all_results

    def scrape_product(self, product_id: str) -> list[dict]:
        """Scrape all competitor URLs for one product."""
        product = PRODUCT_MAP.get(product_id)
        if not product:
            logger.warning(f"Product {product_id} not found in catalogue")
            return []

        results = []
        for url in product.competitor_urls:
            price = self._scrape_url(url, product)
            if price:
                results.append({
                    "product_id":       product.id,
                    "competitor_name":  self._domain(url),
                    "competitor_price": price,
                    "url":              url,
                    "scraped_at":       datetime.utcnow(),
                })
                logger.debug(f"{product.name} @ {self._domain(url)}: ₹{price:,.0f}")
            time.sleep(random.uniform(1, 2))

        return results

    def _scrape_url(self, url: str, product: Product) -> Optional[float]:
        """Dispatch to site-specific parser."""
        try:
            resp = self.session.get(url, timeout=12)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            domain = self._domain(url)
            if "amazon.in" in domain:
                return self._parse_amazon(soup)
            elif "flipkart.com" in domain:
                return self._parse_flipkart(soup)
            elif "myntra.com" in domain:
                return self._parse_myntra(soup)
            elif "nykaa.com" in domain:
                return self._parse_nykaa(soup)
            elif "bigbasket.com" in domain:
                return self._parse_bigbasket(soup)
            elif "jiomart.com" in domain:
                return self._parse_jiomart(soup)
            else:
                return self._parse_generic(soup)

        except Exception as e:
            logger.warning(f"Scrape failed for {url}: {e}")
            return None

    def _parse_amazon(self, soup: BeautifulSoup) -> Optional[float]:
        """Amazon.in price selectors."""
        selectors = [
            "span.a-price-whole",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "span[data-a-color='price'] span.a-offscreen",
            ".a-price .a-offscreen",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return self._clean_price(el.get_text())
        return None

    def _parse_flipkart(self, soup: BeautifulSoup) -> Optional[float]:
        """Flipkart price selectors."""
        selectors = [
            "div._30jeq3._16Jk6d",
            "div._30jeq3",
            "._25b18 ._30jeq3",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return self._clean_price(el.get_text())
        return None

    def _parse_myntra(self, soup: BeautifulSoup) -> Optional[float]:
        """Myntra price selectors."""
        selectors = [
            "span.pdp-price strong",
            ".pdp-discount-container span",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return self._clean_price(el.get_text())
        return None

    def _parse_nykaa(self, soup: BeautifulSoup) -> Optional[float]:
        selectors = ["span.css-111z9ua", "span[class*='price']"]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return self._clean_price(el.get_text())
        return None

    def _parse_bigbasket(self, soup: BeautifulSoup) -> Optional[float]:
        selectors = ["span.discnt-price", "span.sp"]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return self._clean_price(el.get_text())
        return None

    def _parse_jiomart(self, soup: BeautifulSoup) -> Optional[float]:
        selectors = ["span.jm-heading-xxs.jm-mb-xxs", "span.final-price"]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return self._clean_price(el.get_text())
        return None

    def _parse_generic(self, soup: BeautifulSoup) -> Optional[float]:
        """Fallback: try common price schema and meta tags."""
        el = soup.select_one('[itemprop="price"]')
        if el:
            val = el.get("content") or el.get_text()
            return self._clean_price(val)
        return None

    @staticmethod
    def _clean_price(raw: str) -> Optional[float]:
        """Strip ₹, commas, spaces and convert to float."""
        cleaned = ""
        for ch in raw:
            if ch.isdigit() or ch == ".":
                cleaned += ch
        try:
            val = float(cleaned)
            return val if 1 < val < 10_000_000 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _domain(url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
