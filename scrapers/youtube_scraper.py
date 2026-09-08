"""
High-Speed Multi-Threaded YouTube Influencer Scraper Engine.
Scrapes channel details, subscribers, recent videos, engagement metrics,
and parses business contacts (Email, WhatsApp, Instagram, TikTok, Linktree).
Supports fast concurrent execution.
"""

import re
import json
import time
import sys
from typing import Dict, List, Optional, Any, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from config import DEFAULT_HEADERS, MAX_RECENT_VIDEOS_ANALYSIS, generate_niche_queries
from parsers.contact_parser import extract_all_contacts
from parsers.channel_filter import is_blacklisted_channel
from database.db_manager import DatabaseManager


def parse_number_with_suffix(text: str) -> int:
    if not text: return 0
    clean = text.lower().strip()
    clean = re.sub(r'(subscribers?|subscriber|pengikut|penayangan|views?|video|ditonton|x\s*ditonton)', '', clean).strip()
    clean = clean.replace('\xa0', ' ').replace(',', '.')
    multiplier = 1.0
    if 'jt' in clean or 'm' in clean:
        multiplier = 1_000_000.0
        clean = re.sub(r'[jtm]', '', clean).strip()
    elif 'rb' in clean or 'k' in clean:
        multiplier = 1_000.0
        clean = re.sub(r'[rbk]', '', clean).strip()
    elif 'b' in clean:
        multiplier = 1_000_000_000.0
        clean = re.sub(r'[b]', '', clean).strip()

    try:
        match = re.search(r'([0-9]+(?:\.[0-9]+)?)', clean)
        if match: return int(float(match.group(1)) * multiplier)
    except Exception:
        pass
    return 0

class YouTubeScraper:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.db = DatabaseManager()

    def _get_session(self) -> requests.Session:
        session = requests.Session()
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        ]
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
        }
        session.headers.update(headers)
        retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def scrape_channel_direct(self, target: str, category: str = "", keyword: str = "") -> Optional[Dict[str, Any]]:
        session = self._get_session()
        try:
            target = target.strip()
            if target.startswith("http://") or target.startswith("https://"):
                url = target
                if not url.endswith("/videos"): url = f"{url.rstrip('/')}/videos"
            elif target.startswith("UC") and len(target) == 24:
                url = f"https://www.youtube.com/channel/{target}/videos"
            else:
                handle = target if target.startswith("@") else f"@{target}"
                url = f"https://www.youtube.com/{handle}/videos"

            resp = session.get(url, timeout=(5, 15))
            if resp.status_code != 200: return None
            html = resp.text
            match = re.search(r'var ytInitialData = ({.*?});</script>', html) or re.search(r'window\["ytInitialData"\] = ({.*?});', html)
            if not match: return None
            data = json.loads(match.group(1))

            meta = data.get("metadata", {}).get("channelMetadataRenderer", {})
            header = data.get("header", {})

            channel_id = meta.get("externalId", "")
            if not channel_id:
                cid_match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', html)
                if cid_match: channel_id = cid_match.group(1)
            if not channel_id: return None

            channel_title = meta.get("title", "")
            description = meta.get("description", "")
            avatar_url = ""
            if meta.get("avatar", {}).get("thumbnails", []): avatar_url = meta.get("avatar")["thumbnails"][-1].get("url", "")
            custom_url = meta.get("channelUrl") or meta.get("vanityChannelUrl") or f"https://www.youtube.com/channel/{channel_id}"

            handle = ""
            sub_count = 0
            sub_formatted = ""
            total_videos = 0

            phr = header.get("pageHeaderRenderer", {})
            vm = phr.get("content", {}).get("pageHeaderViewModel", {})
            if vm:
                if not channel_title: channel_title = vm.get("title", {}).get("dynamicTextViewModel", {}).get("text", {}).get("content", "")
                for r in vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", []):
                    for p in [x.get("text", {}).get("content", "") for x in r.get("metadataParts", [])]:
                        if p.startswith("@"): handle = p
                        elif "sub" in p.lower() or "pengikut" in p.lower():
                            sub_formatted = p
                            sub_count = parse_number_with_suffix(p)
                        elif "video" in p.lower():
                            total_videos = parse_number_with_suffix(p)

            if not handle:
                hmatch = re.search(r'"canonicalBaseUrl":"(/@[^"]+)"', html)
                if hmatch: handle = hmatch.group(1).lstrip('/')

            if is_blacklisted_channel(channel_title, handle, description): return None

            if sub_count == 0:
                smatch = re.search(r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"\}', html)
                if smatch:
                    sub_formatted = smatch.group(1)
                    sub_count = parse_number_with_suffix(sub_formatted)

            recent_views: List[int] = []
            recent_video_titles: List[str] = []

            tabs = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            for tab in tabs:
                contents = tab.get("tabRenderer", {}).get("content", {}).get("richGridRenderer", {}).get("contents", [])
                for item in contents:
                    if len(recent_views) >= MAX_RECENT_VIDEOS_ANALYSIS: break
                    rir = item.get("richItemRenderer", {}).get("content", {})
                    if "lockupViewModel" in rir:
                        meta_vm = rir["lockupViewModel"].get("metadata", {}).get("lockupMetadataViewModel", {})
                        if v_title := meta_vm.get("title", {}).get("content", ""): recent_video_titles.append(v_title)
                        for row in meta_vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", []):
                            for part in row.get("metadataParts", []):
                                txt = part.get("text", {}).get("content", "")
                                if "ditonton" in txt.lower() or "views" in txt.lower():
                                    if v_views := parse_number_with_suffix(txt): recent_views.append(v_views)
                    elif "videoRenderer" in rir:
                        vr = rir["videoRenderer"]
                        if v_title := vr.get("title", {}).get("runs", [{}])[0].get("text", ""): recent_video_titles.append(v_title)
                        txt = vr.get("viewCountText", {}).get("simpleText") or vr.get("viewCountText", {}).get("runs", [{}])[0].get("text", "")
                        if v_views := parse_number_with_suffix(txt): recent_views.append(v_views)

            avg_views = int(sum(recent_views) / len(recent_views)) if recent_views else 0
            engagement_rate = round((avg_views / sub_count) * 100, 2) if sub_count > 0 and avg_views > 0 else 0.0

            extracted_links = [lk for lk in re.findall(r'href="(https?://[^"]+)"', html) if any(x in lk for x in ["instagram.com", "tiktok.com", "linktr.ee", "beacons.ai", "wa.me", "desty.page", "lynk.id"])]
            contacts = extract_all_contacts(f"{description}\n" + "\n".join(recent_video_titles), extracted_links)
            from parsers.contact_parser import get_influencer_tier

            return {
                "platform": "youtube", "channel_id": channel_id, "channel_title": channel_title or handle or "YouTube Creator",
                "handle": handle or f"@{channel_title.lower().replace(' ', '')}", "custom_url": custom_url,
                "creator_type": contacts["creator_type"], "tier": get_influencer_tier(sub_count), "subscribers": sub_count,
                "subscribers_formatted": sub_formatted or f"{sub_count:,}", "total_videos": total_videos,
                "total_views": 0, "avg_recent_views": avg_views, "avg_recent_likes": 0, "avg_recent_comments": 0,
                "engagement_rate": engagement_rate, "category": category or "General", "search_keyword": keyword,
                "country": "ID", "description": description[:1000] if description else "", "emails": contacts["emails_str"],
                "phone_numbers": contacts["phones_str"], "instagram_handle": contacts["instagram"],
                "tiktok_handle": contacts["tiktok"], "bio_links": contacts["aggregator_links_str"],
                "affiliate_links": contacts["affiliate_links_str"], "avatar_url": avatar_url,
            }
        except Exception:
            return None

    def _search_single_query(self, keyword: str, limit: int = 30) -> List[Tuple[str, str, str]]:
        session = self._get_session()
        candidates = []
        try:
            url = f"https://www.youtube.com/results?search_query={requests.utils.quote(keyword)}"
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                match = re.search(r'var ytInitialData = ({.*?});</script>', resp.text)
                if match:
                    data = json.loads(match.group(1))
                    for sec in data.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", []):
                        for it in sec.get("itemSectionRenderer", {}).get("contents", []):
                            if len(candidates) >= limit: break
                            if "channelRenderer" in it:
                                cr = it["channelRenderer"]
                                c_id = cr.get("channelId")
                                c_title = cr.get("title", {}).get("simpleText", "")
                                c_handle = cr.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("canonicalBaseUrl", "")
                                if c_id and not is_blacklisted_channel(c_title, c_handle):
                                    candidates.append((c_id, c_handle, keyword))
                            elif "videoRenderer" in it:
                                vr = it["videoRenderer"]
                                owner_runs = vr.get("ownerText", {}).get("runs", [])
                                if owner_runs:
                                    owner_name = owner_runs[0].get("text", "")
                                    nav = owner_runs[0].get("navigationEndpoint", {})
                                    c_id = nav.get("browseEndpoint", {}).get("browseId")
                                    c_handle = nav.get("browseEndpoint", {}).get("canonicalBaseUrl", "")
                                    if c_id and c_id.startswith("UC") and not is_blacklisted_channel(owner_name, c_handle):
                                        candidates.append((c_id, c_handle, keyword))
        except Exception: pass
        return candidates

    def scrape_target_count(self, category_name: str, target_count: int = 100, max_threads: int = 6) -> List[Dict[str, Any]]:
        queries = generate_niche_queries(category_name)
        discovered_channel_ids: Set[str] = set()
        candidates_to_process: List[Tuple[str, str, str]] = []
        scraped_results: List[Dict[str, Any]] = []

        print(f"\n============================================================")
        print(f"🎯 MEMULAI TARGET SCRAPING {target_count:,} INFLUENCER YOUTUBE")
        print(f"📂 Kategori: [{category_name}] (Tersedia {len(queries)} topik pencarian)")
        print(f"============================================================")

        needed_candidates = int(target_count * 1.25)
        batch_size = min(len(queries), max(20, int(target_count / 10)))
        query_batch = queries[:batch_size]

        print(f"🔍 Menjalankan pencarian kandidat secara paralel...")

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {executor.submit(self._search_single_query, q): q for q in query_batch}
            for f in as_completed(futures):
                res = f.result()
                for cid, chandle, kw in res:
                    if cid not in discovered_channel_ids:
                        discovered_channel_ids.add(cid)
                        candidates_to_process.append((cid, chandle, kw))

                # Menggantikan tqdm disc dengan print
                print(f"🔍 Sedang mencari... Total Unik Ditemukan: {len(candidates_to_process)}")

        if len(candidates_to_process) < needed_candidates and len(queries) > batch_size:
            extra_batch = queries[batch_size:batch_size + 40]
            print(f"🔄 Menambah batch pencarian...")
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = {executor.submit(self._search_single_query, q): q for q in extra_batch}
                for f in as_completed(futures):
                    res = f.result()
                    for cid, chandle, kw in res:
                        if cid not in discovered_channel_ids:
                            discovered_channel_ids.add(cid)
                            candidates_to_process.append((cid, chandle, kw))

        print(f"✨ Total {len(candidates_to_process):,} calon kreator siap diekstrak!")

        candidates_target = candidates_to_process[:target_count]
        email_count = 0
        wa_count = 0

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_cand = {}
            for cid, chandle, kw in candidates_target:
                time.sleep(random.uniform(0.5, 2.5))
                target_handle = chandle.lstrip('/') if chandle else cid
                future = executor.submit(self.scrape_channel_direct, target_handle, category_name, kw)
                future_to_cand[future] = (cid, chandle)

            for future in as_completed(future_to_cand):
                cid, chandle = future_to_cand[future]
                try:
                    data = future.result()
                    if data:
                        self.db.save_influencer(data)
                        scraped_results.append(data)
                        if data.get("emails"): email_count += 1
                        if data.get("phone_numbers"): wa_count += 1

                        # Menggantikan tqdm scrape dengan print
                        print(f"✅ [YT] Tersimpan: {len(scraped_results)}/{target_count} | Emails: {email_count} | WA: {wa_count}")
                except Exception as e:
                    # Bug fix: menampilkan ID channel jika terjadi error alih-alih menampilkan variabel 'data' yang belum terdefinisi
                    print(f"⚠️ Gagal scrape {chandle or cid}: {str(e)}")

        print(f"\n🎉 Berhasil mengumpulkan {len(scraped_results):,} data influencer kategori '{category_name}'!")
        return scraped_results