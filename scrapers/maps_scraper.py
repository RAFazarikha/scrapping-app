"""
Google Maps Places API Scraper for Manufacturer/Business Leads.
Replaces Playwright with official Google Places Text Search and Place Details APIs.
"""

import os
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any
from parsers.contact_parser import extract_emails

class MapsScraper:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")
        self.session = requests.Session()
        self.keywords = [
            "maklon", "jasa maklon", "perusahaan maklon", "pabrik maklon", "produsen maklon",
            "manufaktur", "manufacturer", "contract manufacturing", "contract manufacturer",
            "manufacturing company", "manufacturing partner", "jasa produksi", "jasa manufaktur",
            "jasa pembuatan produk", "produksi custom", "produksi OEM", "OEM manufacturer",
            "private label", "private label manufacturer", "white label", "custom manufacturing",
            "custom product manufacturer", "production partner"
        ]
        self.fallback_keywords = ["pabrik", "perusahaan", "industri", "jasa", "manufaktur"]

    def _extract_email_from_site(self, url: str) -> str:
        """Performs HTTP GET to extract emails from the business website."""
        if not url or not url.startswith('http'):
            return ""
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                text = soup.get_text()
                emails = extract_emails(text)
                return ", ".join(emails) if emails else ""
        except Exception as e:
            print(f"Email extraction error for {url}: {e}")
        return ""

    def _search_places_api(self, query: str) -> List[str]:
        """Calls Google Places Text Search API and returns a list of place_ids."""
        place_ids = []
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "key": self.api_key
        }
        try:
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status")
                if status == "REQUEST_DENIED":
                    err_msg = data.get("error_message", "API Key tidak valid atau tidak memiliki akses.")
                    raise ValueError(f"Akses Ditolak oleh Google: {err_msg}")
                elif status == "OVER_QUERY_LIMIT":
                    raise ValueError("Kuota API Google Maps terlampaui (Over Query Limit).")
                elif status == "ZERO_RESULTS":
                    return []
                elif status != "OK":
                    err_msg = data.get("error_message", f"Status API: {status}")
                    raise ValueError(f"Google Places API Error: {err_msg}")

                for item in data.get("results", []):
                    pid = item.get("place_id")
                    if pid:
                        place_ids.append(pid)
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            print(f"Places Text Search API error: {e}")
            raise e
        return place_ids

    def _get_place_detail_api(self, place_id: str) -> Dict[str, Any]:
        """Calls Google Places Details API for a given place_id."""
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,geometry,formatted_phone_number,website",
            "key": self.api_key
        }
        try:
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status")
                if status == "REQUEST_DENIED":
                    err_msg = data.get("error_message", "API Key tidak valid.")
                    raise ValueError(f"Akses Ditolak oleh Google: {err_msg}")
                elif status == "OVER_QUERY_LIMIT":
                    raise ValueError("Kuota API Google Maps terlampaui.")
                return data.get("result", {})
        except Exception as e:
            print(f"Place Details API error for {place_id}: {e}")
            raise e
        return {}

    def scrape_keyword(self, keyword: str, location: str, seen_place_ids: set = None) -> List[Dict[str, Any]]:
        """Searches places using Places API, fetches details, and maps fields.
        Deduplicates by place_id using seen_place_ids (shared across keywords)."""
        if seen_place_ids is None:
            seen_place_ids = set()
        results = []
        query = f"{keyword} in {location}"
        place_ids = self._search_places_api(query)

        # Fallback if no results found with primary keyword
        if not place_ids:
            for fk in self.fallback_keywords:
                fallback_query = f"{fk} in {location}"
                place_ids = self._search_places_api(fallback_query)
                if place_ids:
                    keyword = fk
                    break

        for pid in place_ids[:20]:
            # Skip duplicate place_ids (overlapping search areas)
            if pid in seen_place_ids:
                continue
            seen_place_ids.add(pid)

            detail = self._get_place_detail_api(pid)
            if not detail:
                continue

            name = detail.get("name", "")
            address = detail.get("formatted_address", "")
            geometry = detail.get("geometry", {}).get("location", {})
            lat = float(geometry.get("lat", 0.0))
            lon = float(geometry.get("lng", 0.0))
            phone = detail.get("formatted_phone_number", "")
            website = detail.get("website", "")

            # Email extraction
            email = self._extract_email_from_site(website)

            results.append({
                "name": name,
                "address": address,
                "lat": lat,
                "lon": lon,
                "phone": phone,
                "website": website,
                "email": email,
                "category": keyword,
                "search_keyword": keyword,
                "platform": "google_maps",
                "channel_id": f"gmaps_api_{pid}",
                "channel_title": name,
                "handle": name,
                "custom_url": website or f"https://www.google.com/maps/place/?q=place_id:{pid}",
                "tier": "Business",
                "creator_type": "Business",
                "country": "ID",
                "subscribers": 0,
                "subscribers_formatted": "0",
                "total_videos": 0,
                "total_views": 0,
                "avg_recent_views": 0,
                "avg_recent_likes": 0,
                "avg_recent_comments": 0,
                "engagement_rate": 0.0
            })
        return results

    def scrape_target_count(self, category_name: str, target_count: int = 100, location: str = "Jakarta") -> List[Dict[str, Any]]:
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        results = []
        seen_place_ids = set()
        
        all_keywords = [category_name] if category_name in self.keywords else self.keywords
        for kw in all_keywords:
            if len(results) >= target_count:
                break
            for item in self.scrape_keyword(kw, location, seen_place_ids):
                results.append(item)
                db.save_influencer(item)
                print(f"✅ [Maps API] Tersimpan: {len(results)}/{target_count} - {item.get('name', 'Unknown')}")
                if len(results) >= target_count:
                    break
            time.sleep(1)
        return results

if __name__ == "__main__":
    ms = MapsScraper()
    out = ms.scrape_target_count("pabrik", target_count=2, location="Jakarta")
    print(f"OK: {len(out)} results")
