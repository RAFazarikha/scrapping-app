"""
High-Speed Multi-Threaded Instagram Influencer Scraper Engine for Indonesia.
Extracts creator profiles, followers, following, posts, bio, and business contacts (Email, WhatsApp, TikTok, Linktree).
Supports fast concurrent execution with live real-time progress bars.
"""

import re
import html
import time
import sys
from typing import Dict, List, Optional, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tqdm import tqdm
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from parsers.contact_parser import extract_all_contacts, INVALID_HANDLES
from parsers.channel_filter import is_blacklisted_channel
from database.db_manager import DatabaseManager
from scrapers.youtube_scraper import parse_number_with_suffix

IG_CRAWLER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

IG_NICHE_SEEDS = {
    "Kosmetik & Skincare": [
        "tasyafarasya", "abelcantika", "fatyafee", "clarissaputri_", "almirantifira",
        "jharna.bhagwani", "janineintansari", "esterwijaya", "dindasafay", "vinnafitriani",
        "suhaysalim", "rachelvennya", "cathyfacil", "livyrenata", "raisa6690",
        "aurelie.hermansyah", "amandarawles", "nandaarum", "claudianovira", "saritiw",
        "naymaysaa", "nadyaaqilla", "tiarandini", "zivamagnolya", "lyodra",
        "dr.richardlee_official", "dr.kamila_jaidi", "drozindonesiaofficial", "dianutami",
        "reginapoetiray", "jennifercoppenreal20", "tiaracharlotte", "sarwendah29", "ashanty_ash"
    ],
    "Makanan & Kuliner": [
        "mgdalenaf", "tanboy_kun", "kenandgrat", "dimsthemeatguy", "jessicajane99",
        "farida.nurhan", "willgoz", "sibungbung", "marscellalungg", "separuhakulemak",
        "nanakoot", "hendry.jonathan", "dyodoran", "bikinlaper.transtv", "makanlurr",
        "nex_carlos", "kuliner_jakarta", "jktfooddestination", "anakjajan", "eatandtreats",
        "gedeinperut", "jktfoodbang", "kokobuncit", "surabayafoodies", "jogjafoodhunter",
        "arnoldpo", "renattamoeloek", "junarorimpandeyofficial", "hungryfever", "buncitfoodies",
        "riaricis1795", "attahalilintar", "baimwong"
    ],
    "Fashion & Outfit": [
        "fujiiian", "nazlaalifa", "shannongbr", "clarissaputri_", "dindasafay",
        "cissienugraha", "tiqasya", "tasyakissty", "meiraniap", "dwihandaanda",
        "hamidahrachmayanti", "strngrrr", "viratandia", "tarabasro", "tantrinamirah",
        "alghazali7", "jovialdalopez", "andreadianbimo", "nabilagardena", "indpriw",
        "agthpricilla", "febbyrastanty", "enzystoria", "hanggini", "anyageraldine",
        "chikakiku", "amandarawles", "claudianovira", "naymaysaa", "citraciki"
    ],
    "Gadget & Teknologi": [
        "gadgetins", "sobat_hape", "davidbeatt", "jagatreview", "malikgadget",
        "krisnapt", "beritagadget", "putureza", "techbrothers.id", "gaptechid",
        "dhiarcom", "legawagadget", "kutukupret", "benshardware", "techdaily.id",
        "bangripay", "gadgetren", "pricebook", "pemmzchannel", "teknologue",
        "mouldie_satria", "stevenndut", "obby_holic", "infotech.id"
    ]
}


class InstagramScraper:
    def __init__(self):
        self.db = DatabaseManager()

    def _get_session(self) -> requests.Session:
        session = requests.Session()

        # Daftar User-Agent modern untuk dirotasi
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        ]

        # Konfigurasi ulang header
        headers = {
            "User-Agent": random.choice(user_agents), # Rotasi UA
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
        }
        session.headers.update(headers)

        # Mekanisme Backoff (Jeda yang bertambah secara eksponensial saat gagal)
        retries = Retry(
            total=3,  # Maksimal coba lagi 3 kali
            backoff_factor=2,  # Waktu tunggu: 2s, 4s, 8s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def scrape_creator(self, username: str, category: str = "", keyword: str = "") -> Optional[Dict[str, Any]]:
        """Scrapes a single Instagram profile and extracts stats, bio, and business contacts."""
        session = self._get_session()
        try:
            clean_username = username.strip().lstrip('@').replace('https://www.instagram.com/', '').rstrip('/')
            url = f"https://www.instagram.com/{clean_username}/"

            resp = session.get(url, timeout=(5, 15))
            if resp.status_code != 200:
                return None

            html_text = resp.text

            desc_match = re.search(r'<meta\s+(?:property|name)="description"\s+content="([^"]+)"', html_text) or re.search(r'<meta\s+content="([^"]+)"\s+(?:property|name)="description"', html_text)
            if not desc_match:
                desc_match = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]+)"', html_text) or re.search(r'<meta\s+content="([^"]+)"\s+(?:property|name)="og:description"', html_text)

            if not desc_match:
                return None

            raw_desc = html.unescape(desc_match.group(1))

            followers_count = 0
            following_count = 0
            posts_count = 0
            name = clean_username
            handle = f"@{clean_username}"
            bio = ""

            # Multilingual stats parsing (Indonesian: Pengikut/Mengikuti/Postingan, English: Followers/Following/Posts)
            stats_match = re.search(
                r'([0-9.,MKkmb\s]+(?:rb|jt|k|m|b)?)\s*(?:Followers|Pengikut),\s*([0-9.,MKkmb\s]+(?:rb|jt|k|m|b)?)\s*(?:Following|Mengikuti),\s*([0-9.,MKkmb\s]+(?:rb|jt|k|m|b)?)\s*(?:Posts|Postingan|Kiriman)',
                raw_desc,
                re.IGNORECASE
            )
            if stats_match:
                followers_count = parse_number_with_suffix(stats_match.group(1))
                following_count = parse_number_with_suffix(stats_match.group(2))
                posts_count = parse_number_with_suffix(stats_match.group(3))
            else:
                f_match = re.search(r'([0-9.,MKkmb\s]+(?:rb|jt|k|m|b)?)\s*(?:Followers|Pengikut)', raw_desc, re.IGNORECASE)
                if f_match:
                    followers_count = parse_number_with_suffix(f_match.group(1))
                p_match = re.search(r'([0-9.,MKkmb\s]+(?:rb|jt|k|m|b)?)\s*(?:Posts|Postingan|Kiriman)', raw_desc, re.IGNORECASE)
                if p_match:
                    posts_count = parse_number_with_suffix(p_match.group(1))

            if "on Instagram:" in raw_desc:
                bio_part = raw_desc.split("on Instagram:")[-1].strip().strip('"').strip('“').strip('”')
                bio = bio_part
            elif "from" in raw_desc:
                bio = ""

            name_match = re.search(r'-\s+(?:See Instagram photos and videos from\s+)?([^(]+)\s+\(@([^)]+)\)', raw_desc)
            if name_match:
                name = name_match.group(1).strip()
                handle = f"@{name_match.group(2).strip()}"

            # Filter out TV, News, Corporate accounts
            if is_blacklisted_channel(name, handle, bio):
                return None

            if followers_count >= 1_000_000:
                sub_formatted = f"{followers_count/1_000_000:.1f}M followers"
            elif followers_count >= 1_000:
                sub_formatted = f"{followers_count/1_000:.1f}K followers"
            else:
                sub_formatted = f"{followers_count} followers"

            contacts = extract_all_contacts(bio)
            from parsers.contact_parser import get_influencer_tier
            tier = get_influencer_tier(followers_count)

            influencer_data = {
                "platform": "instagram",
                "channel_id": f"ig_{clean_username.lower()}",
                "channel_title": name,
                "handle": handle,
                "custom_url": f"https://www.instagram.com/{clean_username}/",
                "creator_type": contacts["creator_type"],
                "tier": tier,
                "subscribers": followers_count,
                "subscribers_formatted": sub_formatted,
                "total_videos": posts_count,
                "total_views": 0,
                "avg_recent_views": 0,
                "avg_recent_likes": 0,
                "avg_recent_comments": 0,
                "engagement_rate": 0.0,
                "category": category or "General",
                "search_keyword": keyword,
                "country": "ID",
                "description": bio[:1000] if bio else "",
                "emails": contacts["emails_str"],
                "phone_numbers": contacts["phones_str"],
                "instagram_handle": handle,
                "tiktok_handle": contacts["tiktok"],
                "bio_links": contacts["aggregator_links_str"],
                "affiliate_links": contacts["affiliate_links_str"],
                "avatar_url": "",
            }

            return influencer_data

        except Exception:
            return None

    def scrape_target_count(self, category_name: str, target_count: int = 100, max_threads: int = 5) -> List[Dict[str, Any]]:
        """
        High-speed concurrent scraping for Instagram creators.
        Pulls from cross-platform discovery pool + extended seed lists.
        Continues until target_count successful profiles are reached.
        """
        seeds = IG_NICHE_SEEDS.get(category_name, [])
        discovered_pool = self.db.get_unscraped_handles("instagram", category=category_name, limit=5000)

        all_candidates = []
        seen = set()
        for h in seeds + discovered_pool:
            clean = h.strip().lstrip('@').lower()
            if clean and clean not in seen and len(clean) >= 3 and clean not in INVALID_HANDLES:
                seen.add(clean)
                all_candidates.append(clean)

        scraped_results: List[Dict[str, Any]] = []

        print(f"\n============================================================")
        print(f"📸 MEMULAI INSTAGRAM SCRAPING TARGET {target_count:,} INFLUENCER")
        print(f"📂 Kategori: [{category_name}] (Tersedia {len(all_candidates):,} kandidat akun)")
        print(f"⚡ Mode: Multi-Threaded Engine ({max_threads} parallel workers)")
        print(f"============================================================")

        pbar = tqdm(total=target_count, desc=f"Scraping IG {category_name}")

        email_count = 0
        wa_count = 0

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            batch_size = max_threads * 4
            for i in range(0, len(all_candidates), batch_size):
                if len(scraped_results) >= target_count:
                    break

                batch = all_candidates[i:i + batch_size]
                # Ganti blok future_to_username = { ... } dengan ini:
                future_to_username = {}
                for u in batch:
                    # Jeda acak 0.5 hingga 2.5 detik untuk menghindari rate-limit
                    time.sleep(random.uniform(0.5, 2.5))
                    future = executor.submit(self.scrape_creator, u, category_name)
                    future_to_username[future] = u

                for future in as_completed(future_to_username):
                    u = future_to_username[future]
                    try:
                        data = future.result()
                        if data:
                            self.db.save_influencer(data)
                            self.db.mark_handle_scraped("instagram", u)
                            scraped_results.append(data)
                            if data.get("emails"):
                                email_count += 1
                            if data.get("phone_numbers"):
                                wa_count += 1
                            pbar.update(1)
                            if len(scraped_results) >= target_count:
                                break
                    except Exception as e:
                        # Log error untuk evaluasi, jangan ditelan mentah-mentah
                        print(f"⚠️ Gagal scrape {u}: {str(e)}")

                    pbar.set_postfix({"Emails": email_count, "WA": wa_count, "Tersimpan": len(scraped_results)})

        pbar.close()
        print(f"\n🎉 Berhasil mengumpulkan {len(scraped_results):,} data Instagram influencer kategori '{category_name}'!")
        return scraped_results
