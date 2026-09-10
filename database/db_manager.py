"""
Database Manager for Multi-Platform Influencer & Afiliator Scraper (YouTube, TikTok, Instagram).
Handles SQLite connection, table migrations, duplicate-safe upsert operations,
cross-platform discovery pool management, tier classification, and min-followers filtering.
"""

import sqlite3
import re
from typing import Dict, List, Optional, Any
from config import DATABASE_PATH


class DatabaseManager:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes database schema with indexing, tier classification, and unique constraints."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Main Influencers & Afiliators Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS influencers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT DEFAULT 'youtube',
                    channel_id TEXT NOT NULL,
                    channel_title TEXT,
                    handle TEXT,
                    custom_url TEXT,
                    creator_type TEXT DEFAULT 'Influencer & Afiliator',
                    tier TEXT DEFAULT 'Nano (1K-10K)',
                    subscribers INTEGER DEFAULT 0,
                    subscribers_formatted TEXT,
                    total_videos INTEGER DEFAULT 0,
                    total_views INTEGER DEFAULT 0,
                    avg_recent_views INTEGER DEFAULT 0,
                    avg_recent_likes INTEGER DEFAULT 0,
                    avg_recent_comments INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    category TEXT,
                    search_keyword TEXT,
                    country TEXT DEFAULT 'ID',
                    description TEXT,
                    emails TEXT,
                    phone_numbers TEXT,
                    instagram_handle TEXT,
                    tiktok_handle TEXT,
                    bio_links TEXT,
                    affiliate_links TEXT,
                    avatar_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, channel_id)
                );
            """)

            # 2. Cross-Platform Discovered Handles Pool
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discovered_handles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    handle TEXT NOT NULL,
                    category TEXT,
                    source_platform TEXT DEFAULT 'youtube',
                    is_scraped INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, handle)
                );
            """)
            
            # Check and add new columns if migrating existing db
            cursor.execute("PRAGMA table_info(influencers);")
            columns = [row["name"] for row in cursor.fetchall()]
            if "platform" not in columns:
                cursor.execute("ALTER TABLE influencers ADD COLUMN platform TEXT DEFAULT 'youtube';")
            if "creator_type" not in columns:
                cursor.execute("ALTER TABLE influencers ADD COLUMN creator_type TEXT DEFAULT 'Influencer & Afiliator';")
            if "tier" not in columns:
                cursor.execute("ALTER TABLE influencers ADD COLUMN tier TEXT DEFAULT 'Nano';")
            if "affiliate_links" not in columns:
                cursor.execute("ALTER TABLE influencers ADD COLUMN affiliate_links TEXT;")
            if "city" not in columns:
                cursor.execute("ALTER TABLE influencers ADD COLUMN city TEXT DEFAULT 'Indonesia';")
            if "estimated_rate_card" not in columns:
                cursor.execute("ALTER TABLE influencers ADD COLUMN estimated_rate_card TEXT;")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform ON influencers(platform);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON influencers(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_creator_type ON influencers(creator_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tier ON influencers(tier);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscribers ON influencers(subscribers);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails ON influencers(emails);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_city ON influencers(city);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_disc_handles ON discovered_handles(platform, is_scraped);")

            # Normalization migration
            cursor.execute("UPDATE influencers SET category = 'Kosmetik & Skincare' WHERE category = 'Beauty & Skincare'")
            cursor.execute("UPDATE influencers SET category = 'Makanan & Kuliner' WHERE category = 'Food & Kuliner'")
            cursor.execute("UPDATE influencers SET category = 'Gadget & Teknologi' WHERE category = 'Tech & Gadget'")
            cursor.execute("UPDATE influencers SET category = 'Fashion & Outfit' WHERE category = 'Fashion & OOTD'")
            cursor.execute("UPDATE influencers SET platform = 'youtube' WHERE platform IS NULL OR platform = ''")
            cursor.execute("UPDATE influencers SET creator_type = 'Influencer & Afiliator' WHERE creator_type IS NULL OR creator_type = ''")

            # PRD Standard Tier classification migration (Nano, Micro, Macro, Mega)
            cursor.execute("UPDATE influencers SET tier = 'Mega' WHERE subscribers >= 1000000")
            cursor.execute("UPDATE influencers SET tier = 'Macro' WHERE subscribers >= 100000 AND subscribers < 1000000")
            cursor.execute("UPDATE influencers SET tier = 'Micro' WHERE subscribers >= 10000 AND subscribers < 100000")
            cursor.execute("UPDATE influencers SET tier = 'Nano' WHERE subscribers >= 1000 AND subscribers < 10000")
            cursor.execute("UPDATE influencers SET tier = 'Beginner (<1K)' WHERE subscribers < 1000 OR subscribers IS NULL")

            # Media & TV cleanup migration
            cursor.execute("""
                DELETE FROM influencers WHERE 
                    LOWER(channel_title) LIKE '%kompas%' OR
                    LOWER(channel_title) LIKE '%tvone%' OR
                    LOWER(channel_title) LIKE '%tribun%' OR
                    LOWER(channel_title) LIKE '%liputan6%' OR
                    LOWER(channel_title) LIKE '%inews%' OR
                    LOWER(channel_title) LIKE '%trans7%' OR
                    LOWER(channel_title) LIKE '%transtv%' OR
                    LOWER(channel_title) LIKE '%metrotv%' OR
                    LOWER(channel_title) LIKE '%sctv%' OR
                    LOWER(channel_title) LIKE '%rcti%' OR
                    LOWER(channel_title) LIKE '%indosiar%' OR
                    LOWER(channel_title) LIKE '%antaranews%' OR
                    LOWER(channel_title) LIKE '%jawapos%' OR
                    LOWER(channel_title) LIKE '%detikcom%' OR
                    LOWER(channel_title) LIKE '%kumparan%' OR
                    LOWER(channel_title) LIKE '%cnbc%' OR
                    LOWER(channel_title) LIKE '%cnn indonesia%' OR
                    LOWER(channel_title) LIKE '%samsung indonesia%' OR
                    LOWER(channel_title) LIKE '%shopee indonesia%' OR
                    LOWER(channel_title) LIKE '%kementerian%' OR
                    LOWER(handle) LIKE '%kompas%' OR
                    LOWER(handle) LIKE '%tvone%' OR
                    LOWER(handle) LIKE '%tribun%' OR
                    LOWER(handle) LIKE '%inews%' OR
                    LOWER(handle) LIKE '%cnnindonesia%';
            """)
            conn.commit()

    def add_discovered_handle(self, platform: str, handle: str, category: str = "", source_platform: str = "youtube"):
        """Registers an extracted handle (IG/TikTok) into discovery pool for future scraping."""
        if not handle or not platform:
            return
        clean_handle = handle.strip().lstrip('@').lower()
        if not clean_handle or len(clean_handle) < 3 or clean_handle in ["p", "reel", "video", "tag", "explore", "stories", "channel", "account", "direct"]:
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO discovered_handles (platform, handle, category, source_platform)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(platform, handle) DO NOTHING;
            """, (platform.lower(), clean_handle, category, source_platform))
            conn.commit()

    def harvest_handles_from_youtube(self):
        """Scans all YouTube descriptions in DB and populates discovered_handles for TikTok and IG."""
        if getattr(self, "_harvested_done", False):
            return
        self._harvested_done = True
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT description, category FROM influencers WHERE platform = 'youtube'")
            rows = cursor.fetchall()
            
            for row in rows:
                desc = row["description"] or ""
                cat = row["category"] or ""
                if not desc:
                    continue
                # IG matching
                for m in re.findall(r'instagram\.com/([a-zA-Z0-9_.-]{3,30})', desc, re.IGNORECASE):
                    self.add_discovered_handle("instagram", m, cat, "youtube")
                for m in re.findall(r'(?:ig|instagram|insta)\s*[:=\-]?\s*@?([a-zA-Z0-9_.-]{3,30})', desc, re.IGNORECASE):
                    self.add_discovered_handle("instagram", m, cat, "youtube")
                # TikTok matching
                for m in re.findall(r'tiktok\.com/@([a-zA-Z0-9_.-]{3,30})', desc, re.IGNORECASE):
                    self.add_discovered_handle("tiktok", m, cat, "youtube")
                for m in re.findall(r'(?:tiktok|tt)\s*[:=\-]?\s*@?([a-zA-Z0-9_.-]{3,30})', desc, re.IGNORECASE):
                    self.add_discovered_handle("tiktok", m, cat, "youtube")

    def get_unscraped_handles(self, platform: str, category: Optional[str] = None, limit: int = 5000) -> List[str]:
        """
        Retrieves unscraped handles from the cross-platform discovery pool
        AND automatically bridges creator handles from YouTube/Instagram in the same category.
        """
        self.harvest_handles_from_youtube()
        
        handles = []
        seen = set()

        # Stop words & invalid handles filter
        invalid_words = {
            "p", "reel", "reels", "stories", "story", "explore", "tv", "channel", "account",
            "accounts", "direct", "business", "inquiry", "inquiries", "contact", "official",
            "admin", "endorse", "endorsement", "partnership", "gmail", "yahoo", "link",
            "klik", "cek", "info", "dan", "atau", "ke", "di", "dari", "pada", "untuk",
            "ini", "itu", "first", "empt", "subscribe", "subscribers", "video", "videos",
            "youtube", "tiktok", "instagram", "facebook", "twitter", "wa", "whatsapp",
            "shopee", "tokopedia", "lazada", "review", "haul", "spill", "racun", "disini"
        }

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. From discovered_handles table
            query1 = "SELECT handle FROM discovered_handles WHERE platform = ? AND is_scraped = 0"
            params1 = [platform.lower()]
            if category and category.lower() != "all":
                query1 += " AND (category = ? OR category = '' OR category IS NULL)"
                params1.append(category)
            query1 += " LIMIT ?"
            params1.append(limit)
            cursor.execute(query1, params1)
            for row in cursor.fetchall():
                h = row["handle"].strip().lstrip('@').lower()
                if h and len(h) >= 3 and h not in seen and h not in invalid_words:
                    seen.add(h)
                    handles.append(h)

            # 2. Cross-platform propagation from existing influencers in the same category
            query2 = "SELECT handle, instagram_handle, tiktok_handle FROM influencers WHERE 1=1"
            params2 = []
            if category and category.lower() != "all":
                query2 += " AND (category = ? OR category LIKE ?)"
                params2.extend([category, f"%{category[:5]}%"])
            query2 += " LIMIT ?"
            params2.append(limit)
            cursor.execute(query2, params2)
            
            for row in cursor.fetchall():
                for field in ["handle", "instagram_handle", "tiktok_handle"]:
                    val = row[field]
                    if val:
                        clean = val.strip().lstrip('@').lower().rstrip('.)/,')
                        if clean and len(clean) >= 3 and clean not in seen and clean not in invalid_words:
                            seen.add(clean)
                            handles.append(clean)

            return handles[:limit]

    def mark_handle_scraped(self, platform: str, handle: str):
        """Marks handle as scraped in discovery pool."""
        clean_handle = handle.strip().lstrip('@').lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE discovered_handles SET is_scraped = 1 WHERE platform = ? AND handle = ?", (platform.lower(), clean_handle))
            conn.commit()

    def save_influencer(self, data: Dict[str, Any]) -> bool:
        """Insert or update an influencer record, never creating duplicates.
        Returns True if a new row was inserted, False if an existing row was updated.
        """
        if not data.get("channel_id"):
            return False
        data.setdefault("platform", "youtube")
        data.setdefault("creator_type", "Influencer & Afiliator")
        subs = int(data.get("subscribers", 0) or 0)
        if not data.get("tier") or data["tier"] in ["Nano (1K-10K)", "Micro (10K-100K)", "Mid-Tier (100K-500K)", "Macro (500K-1M)", "Mega (>1M)"]:
            from parsers.contact_parser import get_influencer_tier
            data["tier"] = get_influencer_tier(subs)
        from parsers.contact_parser import estimate_rate_card, extract_city
        if not data.get("city") or data["city"] == "Indonesia":
            data["city"] = extract_city(data.get("description", ""))
        if not data.get("estimated_rate_card"):
            rate_info = estimate_rate_card(data["platform"], subs, data["tier"])
            data["estimated_rate_card"] = rate_info["estimated_rate_range"]
        for k in ["emails", "phone_numbers", "instagram_handle", "tiktok_handle", "bio_links", "affiliate_links", "avatar_url"]:
            data.setdefault(k, "")
        cat = data.get("category", "")
        if data.get("instagram_handle"):
            self.add_discovered_handle("instagram", data["instagram_handle"], cat, data["platform"])
        if data.get("tiktok_handle"):
            self.add_discovered_handle("tiktok", data["tiktok_handle"], cat, data["platform"])
        # Upsert using SQLite ON CONFLICT clause – one statement, no pre‑select.
        upsert_sql = """
            INSERT INTO influencers (
                platform, channel_id, channel_title, handle, custom_url,
                creator_type, tier, city, estimated_rate_card, subscribers,
                subscribers_formatted, total_videos, total_views,
                avg_recent_views, avg_recent_likes, avg_recent_comments,
                engagement_rate, category, search_keyword, country,
                description, emails, phone_numbers, instagram_handle,
                tiktok_handle, bio_links, affiliate_links, avatar_url, created_at, updated_at
            ) VALUES (
                :platform, :channel_id, :channel_title, :handle, :custom_url,
                :creator_type, :tier, :city, :estimated_rate_card, :subscribers,
                :subscribers_formatted, :total_videos, :total_views,
                :avg_recent_views, :avg_recent_likes, :avg_recent_comments,
                :engagement_rate, :category, :search_keyword, :country,
                :description, :emails, :phone_numbers, :instagram_handle,
                :tiktok_handle, :bio_links, :affiliate_links, :avatar_url,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT(platform, channel_id) DO UPDATE SET
                channel_title = COALESCE(:channel_title, channel_title),
                handle = COALESCE(:handle, handle),
                custom_url = COALESCE(:custom_url, custom_url),
                creator_type = COALESCE(:creator_type, creator_type),
                tier = COALESCE(:tier, tier),
                city = COALESCE(:city, city),
                estimated_rate_card = COALESCE(:estimated_rate_card, estimated_rate_card),
                subscribers = CASE WHEN :subscribers > 0 THEN :subscribers ELSE subscribers END,
                subscribers_formatted = COALESCE(:subscribers_formatted, subscribers_formatted),
                total_videos = CASE WHEN :total_videos > 0 THEN :total_videos ELSE total_videos END,
                total_views = CASE WHEN :total_views > 0 THEN :total_views ELSE total_views END,
                avg_recent_views = CASE WHEN :avg_recent_views > 0 THEN :avg_recent_views ELSE avg_recent_views END,
                avg_recent_likes = CASE WHEN :avg_recent_likes > 0 THEN :avg_recent_likes ELSE avg_recent_likes END,
                avg_recent_comments = CASE WHEN :avg_recent_comments > 0 THEN :avg_recent_comments ELSE avg_recent_comments END,
                engagement_rate = CASE WHEN :engagement_rate > 0.0 THEN :engagement_rate ELSE engagement_rate END,
                category = CASE WHEN :category != '' THEN :category ELSE category END,
                emails = CASE WHEN :emails != '' THEN :emails ELSE emails END,
                phone_numbers = CASE WHEN :phone_numbers != '' THEN :phone_numbers ELSE phone_numbers END,
                instagram_handle = CASE WHEN :instagram_handle != '' THEN :instagram_handle ELSE instagram_handle END,
                tiktok_handle = CASE WHEN :tiktok_handle != '' THEN :tiktok_handle ELSE tiktok_handle END,
                bio_links = CASE WHEN :bio_links != '' THEN :bio_links ELSE bio_links END,
                affiliate_links = CASE WHEN :affiliate_links != '' THEN :affiliate_links ELSE affiliate_links END,
                avatar_url = COALESCE(:avatar_url, avatar_url),
                updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(upsert_sql, data)
            conn.commit()
            # cursor.rowcount == 1 for insert, >1 for update (SQLite returns 0 for no change)
            return cursor.rowcount == 1


    def get_all_influencers(
        self,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        has_email: bool = False,
        creator_type: Optional[str] = None,
        tier: Optional[str] = None,
        min_followers: int = 0,
        sort_by: str = "subscribers",
        reverse: bool = True
    ) -> List[Dict[str, Any]]:
        """Retrieves influencers & afiliators with optional filtering and sorting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM influencers WHERE 1=1"
            params = []

            if platform and platform.lower() != "all":
                query += " AND LOWER(platform) = LOWER(?)"
                params.append(platform)

            if category and category.lower() != "all":
                query += " AND (LOWER(category) = LOWER(?) OR LOWER(category) LIKE ?)"
                params.extend([category, f"%{category.lower()[:5]}%"])

            if creator_type and creator_type.lower() != "all":
                query += " AND LOWER(creator_type) LIKE ?"
                params.append(f"%{creator_type.lower()}%")

            if tier and tier.lower() != "all":
                query += " AND LOWER(tier) LIKE ?"
                params.append(f"%{tier.lower()}%")

            if min_followers > 0:
                query += " AND subscribers >= ?"
                params.append(min_followers)

            if has_email:
                query += " AND emails != '' AND emails IS NOT NULL"

        # Dynamic sorting
        allowed_sorts = {"subscribers", "channel_title", "engagement_rate", "category",
                         "handle", "tier", "emails", "phone_numbers"}
        sort_col = sort_by if sort_by in allowed_sorts else "subscribers"
        direction = "DESC" if reverse else "ASC"
        query += f" ORDER BY {sort_col} {direction}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistical overview of the database grouped by platform, category, tier, and creator type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM influencers")
            total_creators = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM influencers WHERE emails != '' AND emails IS NOT NULL")
            creators_with_email = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM influencers WHERE phone_numbers != '' AND phone_numbers IS NOT NULL")
            creators_with_phone = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM influencers WHERE instagram_handle != '' AND instagram_handle IS NOT NULL")
            creators_with_instagram = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM influencers WHERE tiktok_handle != '' AND tiktok_handle IS NOT NULL")
            creators_with_tiktok = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM influencers WHERE affiliate_links != '' AND affiliate_links IS NOT NULL")
            creators_with_affiliate = cursor.fetchone()[0]

            cursor.execute("SELECT platform, COUNT(*) as count FROM influencers GROUP BY platform ORDER BY count DESC")
            by_platform = {row["platform"] or "youtube": row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT tier, COUNT(*) as count FROM influencers GROUP BY tier ORDER BY count DESC")
            by_tier = {row["tier"] or "Nano (1K-10K)": row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT creator_type, COUNT(*) as count FROM influencers GROUP BY creator_type ORDER BY count DESC")
            by_type = {row["creator_type"] or "Influencer & Afiliator": row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT category, COUNT(*) as count FROM influencers GROUP BY category ORDER BY count DESC")
            by_category = {row["category"] or "Uncategorized": row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT platform, COUNT(*) as count FROM discovered_handles WHERE is_scraped = 0 GROUP BY platform")
            unscraped_pool = {row["platform"]: row["count"] for row in cursor.fetchall()}

            return {
                "total_creators": total_creators,
                "creators_with_email": creators_with_email,
                "creators_with_phone": creators_with_phone,
                "creators_with_instagram": creators_with_instagram,
                "creators_with_tiktok": creators_with_tiktok,
                "creators_with_affiliate": creators_with_affiliate,
                "by_platform": by_platform,
                "by_tier": by_tier,
                "by_type": by_type,
                "by_category": by_category,
                "unscraped_discovery_pool": unscraped_pool
            }
