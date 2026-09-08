"""
High-Speed Multi-Threaded TikTok Influencer Scraper Engine for Indonesia.
Extracts creator profiles, followers, total likes, video count, engagement rate,
and parses business contacts (Email, WhatsApp, Instagram, Linktree).
Supports fast concurrent execution with live real-time progress bars.
"""

import re
import json
import time
import sys
from typing import Dict, List, Optional, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from parsers.contact_parser import extract_all_contacts, INVALID_HANDLES
from parsers.channel_filter import is_blacklisted_channel
from database.db_manager import DatabaseManager
from scrapers.youtube_scraper import parse_number_with_suffix

TIKTOK_MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}

TIKTOK_NICHE_SEEDS = {
    "Kosmetik & Skincare": [
        "tasyafarasya", "jharna.bhagwani", "jhonsinaga21", "janineintansari", "almirantifira",
        "fatyafee", "clarissaputri_", "abelcantika", "dindasafay", "esterwijaya",
        "raisa6690", "aurelie.hermansyah", "cathyfacil", "livyrenata", "louissescarlettfamily",
        "tiarandini", "zivamagnolya", "lyodra", "amandarawles", "fujiiian", "nandaarum",
        "suhaysalim", "vinnafitriani", "saritiw", "claudianovira", "naymaysaa", "nadyaaqilla",
        "dr.richard_lee", "dr.tirtakandhi", "dr.kamila_jaidi", "drozindonesia", "skincarebyjessi",
        "dianutami_", "reginapoetiray", "jennifercoppenreal20", "tiaracharlotte", "chikakiku",
        "shabirasunset", "devinaaurel", "sarwendah29", "ashantyhermansyah", "gisella_anastasia"
    ],
    "Makanan & Kuliner": [
        "tanboy_kun", "mgdalenaf", "kenandgrat", "dimsthemeatguy", "jessicajane99",
        "farida.nurhan", "willgoz", "makanlurr", "sibungbung", "marscellalungg",
        "kuliner1menit", "separuhakulemak", "nanakoot", "hendry.jonathan", "dyodoran",
        "foodies.jakarta", "streetfoodindo", "kulinerkotasolo", "bikinlaper.transtv", "nex_carlos",
        "anakjajan", "eatandtreats", "gedeinperut", "jktfoodbang", "kokobuncit",
        "chefarnoldpoernomo", "renattamoeloek", "junarorimpandey", "makanbarenghoki", "hungryfever",
        "buncitfoodies", "perutkarets", "riaricis", "atta.halilintar", "baimwong"
    ],
    "Fashion & Outfit": [
        "fujiiian", "shannongbr", "clarissaputri_", "dindasafay", "nazlaalifa",
        "cissienugraha", "tiqasya", "tasyakissty", "meiraniap", "dwihandaanda",
        "nabilagardena", "hamidahrachmayanti", "strngrrr", "viratandia", "aurelie.hermansyah",
        "jovialdalopez", "andreadianbimo", "tarabasro", "tantrinamirah", "alghazali7",
        "indpriw", "agthpricilla", "febbyrastanty", "enzystoria", "hanggini",
        "anyageraldine", "chikakiku", "amandarawles", "claudianovira", "naymaysaa"
    ],
    "Gadget & Teknologi": [
        "gadgetin", "sobat_hape", "davidbeatt", "malikgadget", "jagatreview",
        "krisnapt", "beritagadget", "putu.reza", "techbrothers.id", "gaptechid",
        "dhiarcom", "legawa.gadget", "kutukupret", "bens_hardware", "techdaily.id",
        "bangripay", "gadgetren", "pricebook", "pemmzchannel", "teknologue",
        "mouldie_satria", "stevenndut", "obby_holic", "infotech.id", "gadgetfight"
    ]
}


class TikTokScraper:
    def __init__(self):
        self.db = DatabaseManager()
        self.session = self._get_session()

    def _get_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(TIKTOK_MOBILE_HEADERS)
        return s

    def scrape_creator(self, username: str, category: str = "", keyword: str = "") -> Optional[Dict[str, Any]]:
        """Scrapes a single TikTok profile and extracts stats, bio, and business contacts."""
        session = self._get_session()
        try:
            clean_username = username.strip().lstrip('@').replace('https://www.tiktok.com/@', '').rstrip('/')
            url = f"https://www.tiktok.com/@{clean_username}"

            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            html_text = resp.text

            match = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">({.*?})</script>', html_text)
            if not match:
                return None

            data = json.loads(match.group(1))
            user_detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
            user_info = user_detail.get("userInfo", {})
            user = user_info.get("user", {})
            stats = user_info.get("stats", {})

            if not user.get("uniqueId"):
                return None

            unique_id = user.get("uniqueId")
            nickname = user.get("nickname") or unique_id
            signature = user.get("signature", "")

            # Filter out TV, News, Corporate accounts
            if is_blacklisted_channel(nickname, unique_id, signature):
                return None
            avatar_url = user.get("avatarLarger") or user.get("avatarMedium", "")

            follower_count = int(stats.get("followerCount", 0))
            following_count = int(stats.get("followingCount", 0))
            heart_count = int(stats.get("heartCount", 0) or stats.get("heart", 0))
            video_count = int(stats.get("videoCount", 0))

            avg_views = int(heart_count / max(1, video_count)) if video_count > 0 else 0
            engagement_rate = 0.0
            if follower_count > 0 and avg_views > 0:
                engagement_rate = round((avg_views / follower_count) * 100, 2)

            bio_link = user.get("bioLink", {}).get("link", "")
            external_links = [bio_link] if bio_link else []
            contacts = extract_all_contacts(signature, external_links)
            from parsers.contact_parser import get_influencer_tier
            tier = get_influencer_tier(follower_count)

            if follower_count >= 1_000_000:
                sub_formatted = f"{follower_count/1_000_000:.1f}M followers"
            elif follower_count >= 1_000:
                sub_formatted = f"{follower_count/1_000:.1f}K followers"
            else:
                sub_formatted = f"{follower_count} followers"

            influencer_data = {
                "platform": "tiktok",
                "channel_id": f"tt_{user.get('id', unique_id)}",
                "channel_title": nickname,
                "handle": f"@{unique_id}",
                "custom_url": f"https://www.tiktok.com/@{unique_id}",
                "creator_type": contacts["creator_type"],
                "tier": tier,
                "subscribers": follower_count,
                "subscribers_formatted": sub_formatted,
                "total_videos": video_count,
                "total_views": heart_count,
                "avg_recent_views": avg_views,
                "avg_recent_likes": avg_views,
                "avg_recent_comments": 0,
                "engagement_rate": engagement_rate,
                "category": category or "General",
                "search_keyword": keyword,
                "country": "ID",
                "description": signature[:1000] if signature else "",
                "emails": contacts["emails_str"],
                "phone_numbers": contacts["phones_str"],
                "instagram_handle": contacts["instagram"],
                "tiktok_handle": f"@{unique_id}",
                "bio_links": contacts["aggregator_links_str"] or bio_link,
                "affiliate_links": contacts["affiliate_links_str"],
                "avatar_url": avatar_url,
            }

            return influencer_data

        except Exception:
            return None

    def scrape_target_count(self, category_name: str, target_count: int = 100, max_threads: int = 5) -> List[Dict[str, Any]]:
        """
        High-speed concurrent scraping for TikTok creators.
        Pulls from cross-platform discovery pool + extended seed lists.
        Continues until target_count successful profiles are reached.
        """
        seeds = TIKTOK_NICHE_SEEDS.get(category_name, [])
        discovered_pool = self.db.get_unscraped_handles("tiktok", category=category_name, limit=5000)
        
        all_candidates = []
        seen = set()
        for h in seeds + discovered_pool:
            clean = h.strip().lstrip('@').lower()
            if clean and clean not in seen and len(clean) >= 3 and clean not in INVALID_HANDLES:
                seen.add(clean)
                all_candidates.append(clean)

        scraped_results: List[Dict[str, Any]] = []

        print(f"\n============================================================")
        print(f"🎵 MEMULAI TIKTOK SCRAPING TARGET {target_count:,} INFLUENCER")
        print(f"📂 Kategori: [{category_name}] (Tersedia {len(all_candidates):,} kandidat akun)")
        print(f"⚡ Mode: Multi-Threaded Engine ({max_threads} parallel workers)")
        print(f"============================================================")

        pbar = tqdm(total=target_count, desc=f"Scraping TikTok {category_name}")
        
        email_count = 0
        wa_count = 0

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            batch_size = max_threads * 4
            for i in range(0, len(all_candidates), batch_size):
                if len(scraped_results) >= target_count:
                    break

                batch = all_candidates[i:i + batch_size]
                future_to_username = {
                    executor.submit(self.scrape_creator, u, category_name): u
                    for u in batch
                }

                for future in as_completed(future_to_username):
                    u = future_to_username[future]
                    try:
                        data = future.result()
                        if data:
                            self.db.save_influencer(data)
                            self.db.mark_handle_scraped("tiktok", u)
                            scraped_results.append(data)
                            if data.get("emails"):
                                email_count += 1
                            if data.get("phone_numbers"):
                                wa_count += 1
                            pbar.update(1)
                            if len(scraped_results) >= target_count:
                                break
                    except Exception:
                        pass

                    pbar.set_postfix({"Emails": email_count, "WA": wa_count, "Tersimpan": len(scraped_results)})

        pbar.close()
        print(f"\n🎉 Berhasil mengumpulkan {len(scraped_results):,} data TikTok influencer kategori '{category_name}'!")
        return scraped_results
