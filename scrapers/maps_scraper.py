"""
Google Maps Place Scraper for Manufacturer/Business Leads (via OpenStreetMap Nominatim).
Extracts company profiles (Maklon, Manufacturer, Custom Production, etc.).
"""

import time
from typing import Dict, List, Any
import requests

class MapsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.keywords = [
            "maklon", "jasa maklon", "perusahaan maklon", "pabrik maklon", "produsen maklon",
            "manufaktur", "manufacturer", "contract manufacturing", "contract manufacturer",
            "manufacturing company", "manufacturing partner", "jasa produksi", "jasa manufaktur",
            "jasa pembuatan produk", "produksi custom", "produksi OEM", "OEM manufacturer",
            "private label", "private label manufacturer", "white label", "custom manufacturing",
            "custom product manufacturer", "production partner"
        ]
        # Fallback keywords that OSM typically has data for
        self.fallback_keywords = ["pabrik", "perusahaan", "industri", "jasa", "manufaktur"]

    def _search_osm(self, keyword: str, location: str) -> List[Dict[str, Any]]:
        """Search using OpenStreetMap Nominatim API."""
        results = []
        params = {
            "q": f"{keyword} {location}",
            "format": "json",
            "addressdetails": 1,
            "limit": 20,
            "extratags": 1,
            "namedetails": 1,
            "countrycodes": "id"
        }
        try:
            r = self.session.get("https://nominatim.openstreetmap.org/search", params=params, timeout=15)
            if r.status_code != 200:
                return results
            for item in r.json():
                addr = item.get("address") or {}
                results.append({
                    "name": item.get("name", ""),
                    "display_name": item.get("display_name", ""),
                    "category": keyword,
                    "address": addr.get("road", ""),
                    "city": location,
                    "state": addr.get("state", ""),
                    "country": addr.get("country", "Indonesia"),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                    "osm_id": item.get("osm_id"),
                    "osm_type": item.get("osm_type"),
                    "description": item.get("display_name", ""),
                    "website": (item.get("extratags") or {}).get("website", ""),
                    "phone": (item.get("extratags") or {}).get("phone", ""),
                    "email": "",
                    "handle": item.get("name") or "unknown",
                    "channel_title": item.get("name") or "Unknown",
                    "channel_id": f"gmaps_{item.get('osm_type', 'n')}_{item.get('osm_id', 0)}",
                    "custom_url": f"https://www.openstreetmap.org/{item.get('osm_type', '')}/{item.get('osm_id', '')}",
                    "subscribers": 0,
                    "subscribers_formatted": "0",
                    "total_videos": 0,
                    "total_views": 0,
                    "avg_recent_views": 0,
                    "avg_recent_likes": 0,
                    "avg_recent_comments": 0,
                    "engagement_rate": 0.0,
                    "tier": "Business",
                    "platform": "google_maps",
                    "creator_type": "Business",
                    "search_keyword": keyword,
                    "country": "ID",
                    "bio_links": (item.get("extratags") or {}).get("website", ""),
                    "affiliate_links": "",
                    "avatar_url": "",
                })
        except Exception as e:
            print(f"OSM error: {e}")
        return results

    def scrape_keyword(self, keyword: str, location: str) -> List[Dict[str, Any]]:
        """Scrape businesses for one keyword in one location, with fallback."""
        results = self._search_osm(keyword, location)
        if results:
            return results
        # Fallback to generic keywords
        for fk in self.fallback_keywords:
            results = self._search_osm(fk, location)
            if results:
                # Mark as belonging to original keyword
                for r in results:
                    r["category"] = keyword
                    r["search_keyword"] = keyword
                return results
        return results

    def scrape_target_count(self, category_name: str, target_count: int = 100, location: str = "Jakarta") -> List[Dict[str, Any]]:
        """Main entry: scrape using keyword with fallback, save to DB, dedupe."""
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        results = []
        seen = set()
        # Try primary keyword first
        all_keywords = [category_name] if category_name in self.keywords else self.keywords
        for kw in all_keywords:
            if len(results) >= target_count:
                break
            for item in self.scrape_keyword(kw, location):
                key = item.get("channel_id")
                key2 = (item.get("name"), item.get("lat"), item.get("lon"))
                if key in seen or key2 in seen:
                    continue
                seen.add(key)
                seen.add(key2)
                results.append(item)
                db.save_influencer(item)
                print(f"✅ [Maps] Tersimpan: {len(results)}/{target_count} - {item.get('name', 'Unknown')}")
                if len(results) >= target_count:
                    break
            time.sleep(1.1)  # ponytail: Nominatim free tier max 1 req/s
        print(f"\n🎉 Berhasil mengumpulkan {len(results):,} data dari [{location}]!")
        return results


if __name__ == "__main__":
    # Self-check
    ms = MapsScraper()
    out = ms.scrape_target_count("pabrik", target_count=5, location="Jakarta")
    assert isinstance(out, list)
    print(f"OK: {len(out)} results")