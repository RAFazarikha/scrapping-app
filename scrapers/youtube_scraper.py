"""
High-Speed Multi-Threaded YouTube Influencer Scraper Engine.
Scrapes channel details, subscribers, recent videos, engagement metrics,
and parses business contacts (Email, WhatsApp, Instagram, TikTok, Linktree).
Supports fast concurrent execution (up to 1,000+ creators) with live real-time progress bars.
"""

import re
import json
import time
import sys
from typing import Dict, List, Optional, Any, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from config import DEFAULT_HEADERS, MAX_RECENT_VIDEOS_ANALYSIS, generate_niche_queries
from parsers.contact_parser import extract_all_contacts
from parsers.channel_filter import is_blacklisted_channel
from database.db_manager import DatabaseManager


def parse_number_with_suffix(text: str) -> int:
    """
    Parses numbers with suffixes like '1.25M', '450 rb', '10.5K', '2,4 jt'.
    Supports both Indonesian (rb, jt) and English (k, m, b) formats.
    """
    if not text:
        return 0
    
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
        if match:
            val = float(match.group(1))
            return int(val * multiplier)
    except Exception:
        pass
    
    return 0


class YouTubeScraper:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.db = DatabaseManager()

    def _get_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(DEFAULT_HEADERS)
        return s

    def scrape_channel_direct(self, target: str, category: str = "", keyword: str = "") -> Optional[Dict[str, Any]]:
        """
        Scrapes a single YouTube channel's details and recent video metrics directly.
        Target can be a handle (e.g. '@GadgetIn'), channel ID (e.g. 'UC...'), or URL.
        """
        session = self._get_session()
        try:
            target = target.strip()
            if target.startswith("http://") or target.startswith("https://"):
                url = target
                if not url.endswith("/videos"):
                    url = f"{url.rstrip('/')}/videos"
            elif target.startswith("UC") and len(target) == 24:
                url = f"https://www.youtube.com/channel/{target}/videos"
            else:
                handle = target if target.startswith("@") else f"@{target}"
                url = f"https://www.youtube.com/{handle}/videos"

            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            html = resp.text

            match = re.search(r'var ytInitialData = ({.*?});</script>', html)
            if not match:
                match = re.search(r'window\["ytInitialData"\] = ({.*?});', html)
            if not match:
                return None

            data = json.loads(match.group(1))

            # 1. Metadata Extraction
            meta = data.get("metadata", {}).get("channelMetadataRenderer", {})
            header = data.get("header", {})
            
            channel_id = meta.get("externalId", "")
            if not channel_id:
                cid_match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', html)
                if cid_match:
                    channel_id = cid_match.group(1)

            if not channel_id:
                return None

            channel_title = meta.get("title", "")
            description = meta.get("description", "")
            
            avatar_url = ""
            avatars = meta.get("avatar", {}).get("thumbnails", [])
            if avatars:
                avatar_url = avatars[-1].get("url", "")

            custom_url = meta.get("channelUrl") or meta.get("vanityChannelUrl") or f"https://www.youtube.com/channel/{channel_id}"
            handle = ""

            # 2. Extract Header Info (Subscribers, Total Videos, Handle)
            sub_count = 0
            sub_formatted = ""
            total_videos = 0

            phr = header.get("pageHeaderRenderer", {})
            vm = phr.get("content", {}).get("pageHeaderViewModel", {})
            
            if vm:
                if not channel_title:
                    channel_title = vm.get("title", {}).get("dynamicTextViewModel", {}).get("text", {}).get("content", "")
                
                meta_rows = vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
                for r in meta_rows:
                    parts = [p.get("text", {}).get("content", "") for p in r.get("metadataParts", [])]
                    for p in parts:
                        p_lower = p.lower()
                        if p.startswith("@"):
                            handle = p
                        elif "sub" in p_lower or "pengikut" in p_lower:
                            sub_formatted = p
                            sub_count = parse_number_with_suffix(p)
                        elif "video" in p_lower:
                            total_videos = parse_number_with_suffix(p)

            # 1. Filter out TV stations, news broadcast networks, and corporate accounts
            if is_blacklisted_channel(channel_title, handle, description):
                return None

            # Fallback for handle
            if not handle:
                handle_match = re.search(r'"canonicalBaseUrl":"(/@[^"]+)"', html)
                if handle_match:
                    handle = handle_match.group(1).lstrip('/')

            if is_blacklisted_channel(channel_title, handle, description):
                return None

            # Fallback for subscribers
            if sub_count == 0:
                sub_match = re.search(r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"\}', html)
                if sub_match:
                    sub_formatted = sub_match.group(1)
                    sub_count = parse_number_with_suffix(sub_formatted)

            # 3. Extract Recent Videos & Metrics
            recent_views: List[int] = []
            recent_video_titles: List[str] = []

            tabs = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            for tab in tabs:
                tr = tab.get("tabRenderer", {})
                if "richGridRenderer" in tr.get("content", {}):
                    contents = tr["content"]["richGridRenderer"].get("contents", [])
                    for item in contents:
                        if len(recent_views) >= MAX_RECENT_VIDEOS_ANALYSIS:
                            break
                        
                        rir = item.get("richItemRenderer", {}).get("content", {})
                        
                        if "lockupViewModel" in rir:
                            lvm = rir["lockupViewModel"]
                            meta_vm = lvm.get("metadata", {}).get("lockupMetadataViewModel", {})
                            v_title = meta_vm.get("title", {}).get("content", "")
                            if v_title:
                                recent_video_titles.append(v_title)

                            snippets = meta_vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
                            for row in snippets:
                                for part in row.get("metadataParts", []):
                                    txt = part.get("text", {}).get("content", "")
                                    if "ditonton" in txt.lower() or "views" in txt.lower():
                                        v_views = parse_number_with_suffix(txt)
                                        if v_views > 0:
                                            recent_views.append(v_views)

                        elif "videoRenderer" in rir:
                            vr = rir["videoRenderer"]
                            v_title = vr.get("title", {}).get("runs", [{}])[0].get("text", "")
                            if v_title:
                                recent_video_titles.append(v_title)
                            v_views_text = vr.get("viewCountText", {}).get("simpleText") or vr.get("viewCountText", {}).get("runs", [{}])[0].get("text", "")
                            v_views = parse_number_with_suffix(v_views_text)
                            if v_views > 0:
                                recent_views.append(v_views)

            avg_views = int(sum(recent_views) / len(recent_views)) if recent_views else 0

            engagement_rate = 0.0
            if sub_count > 0 and avg_views > 0:
                engagement_rate = round((avg_views / sub_count) * 100, 2)

            # 4. Extract External Links & Contacts
            extracted_links = []
            link_matches = re.findall(r'href="(https?://[^"]+)"', html)
            for lk in link_matches:
                if any(x in lk for x in ["instagram.com", "tiktok.com", "linktr.ee", "beacons.ai", "wa.me", "desty.page", "lynk.id"]):
                    extracted_links.append(lk)

            combined_text = f"{description}\n" + "\n".join(recent_video_titles)
            contacts = extract_all_contacts(combined_text, extracted_links)

            from parsers.contact_parser import get_influencer_tier
            tier = get_influencer_tier(sub_count)

            influencer_data = {
                "platform": "youtube",
                "channel_id": channel_id,
                "channel_title": channel_title or handle or "YouTube Creator",
                "handle": handle or f"@{channel_title.lower().replace(' ', '')}",
                "custom_url": custom_url,
                "creator_type": contacts["creator_type"],
                "tier": tier,
                "subscribers": sub_count,
                "subscribers_formatted": sub_formatted or f"{sub_count:,}",
                "total_videos": total_videos,
                "total_views": 0,
                "avg_recent_views": avg_views,
                "avg_recent_likes": 0,
                "avg_recent_comments": 0,
                "engagement_rate": engagement_rate,
                "category": category or "General",
                "search_keyword": keyword,
                "country": "ID",
                "description": description[:1000] if description else "",
                "emails": contacts["emails_str"],
                "phone_numbers": contacts["phones_str"],
                "instagram_handle": contacts["instagram"],
                "tiktok_handle": contacts["tiktok"],
                "bio_links": contacts["aggregator_links_str"],
                "affiliate_links": contacts["affiliate_links_str"],
                "avatar_url": avatar_url,
            }

            return influencer_data

        except Exception:
            return None

    def _search_single_query(self, keyword: str, limit: int = 30) -> List[Tuple[str, str, str]]:
        """Worker function for searching a single query."""
        session = self._get_session()
        candidates = []
        try:
            url = f"https://www.youtube.com/results?search_query={requests.utils.quote(keyword)}"
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                match = re.search(r'var ytInitialData = ({.*?});</script>', resp.text)
                if match:
                    data = json.loads(match.group(1))
                    sections = data.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", [])
                    for sec in sections:
                        items = sec.get("itemSectionRenderer", {}).get("contents", [])
                        for it in items:
                            if len(candidates) >= limit:
                                break
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
        except Exception:
            pass
        return candidates

    def scrape_target_count(self, category_name: str, target_count: int = 100, max_threads: int = 6) -> List[Dict[str, Any]]:
        """
        High-speed concurrent scraping up to target_count (e.g. 500, 1000+).
        Uses ThreadPoolExecutor for fast parallel search & parallel channel extraction.
        """
        queries = generate_niche_queries(category_name)
        discovered_channel_ids: Set[str] = set()
        candidates_to_process: List[Tuple[str, str, str]] = []
        scraped_results: List[Dict[str, Any]] = []

        print(f"\n============================================================")
        print(f"🎯 MEMULAI TARGET SCRAPING {target_count:,} INFLUENCER YOUTUBE")
        print(f"📂 Kategori: [{category_name}] (Tersedia {len(queries)} topik pencarian)")
        print(f"⚡ Mode: Multi-Threaded Engine ({max_threads} parallel workers)")
        print(f"============================================================")

        # 1. Fast Parallel Discovery with Live Progress Bar
        needed_candidates = int(target_count * 1.25)
        batch_size = min(len(queries), max(20, int(target_count / 10)))
        query_batch = queries[:batch_size]

        print(f"🔍 Menjalankan pencarian kandidat secara paralel ({len(query_batch)} query)...")
        pbar_disc = tqdm(total=len(query_batch), desc="[1/2] Pencarian Kandidat")

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {executor.submit(self._search_single_query, q): q for q in query_batch}
            for f in as_completed(futures):
                res = f.result()
                for cid, chandle, kw in res:
                    if cid not in discovered_channel_ids:
                        discovered_channel_ids.add(cid)
                        candidates_to_process.append((cid, chandle, kw))
                pbar_disc.set_postfix({"Unik Ditemukan": f"{len(candidates_to_process):,}"})
                pbar_disc.update(1)

        pbar_disc.close()

        # If needed more candidates for 1,000 target, run next batch
        if len(candidates_to_process) < needed_candidates and len(queries) > batch_size:
            extra_batch = queries[batch_size:batch_size + 40]
            print(f"🔄 Menambah batch pencarian ({len(extra_batch)} query tambahan)...")
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = {executor.submit(self._search_single_query, q): q for q in extra_batch}
                for f in as_completed(futures):
                    res = f.result()
                    for cid, chandle, kw in res:
                        if cid not in discovered_channel_ids:
                            discovered_channel_ids.add(cid)
                            candidates_to_process.append((cid, chandle, kw))

        print(f"✨ Total {len(candidates_to_process):,} calon kreator unik siap diekstrak!")
        print(f"⏳ Memulai ekstraksi detail profil, metrik views, & kontak bisnis...\n")

        # 2. Fast Parallel Channel Extraction with Live Progress Bar
        candidates_target = candidates_to_process[:target_count]
        pbar_scrape = tqdm(total=len(candidates_target), desc=f"[2/2] Scraping {category_name}")
        
        email_count = 0
        wa_count = 0

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_cand = {
                executor.submit(
                    self.scrape_channel_direct,
                    chandle.lstrip('/') if chandle else cid,
                    category_name,
                    kw
                ): (cid, chandle) for cid, chandle, kw in candidates_target
            }

            for future in as_completed(future_to_cand):
                try:
                    data = future.result()
                    if data:
                        self.db.save_influencer(data)
                        scraped_results.append(data)
                        if data.get("emails"):
                            email_count += 1
                        if data.get("phone_numbers"):
                            wa_count += 1
                except Exception:
                    pass

                pbar_scrape.set_postfix({"Emails": email_count, "WA": wa_count, "Tersimpan": len(scraped_results)})
                pbar_scrape.update(1)

        pbar_scrape.close()
        print(f"\n🎉 Berhasil mengumpulkan {len(scraped_results):,} data influencer kategori '{category_name}'!")
        return scraped_results
