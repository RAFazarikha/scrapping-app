"""
Exporter Module for Multi-Platform Influencer & Afiliator Database (YouTube, TikTok, Instagram).
Formats export filenames strictly as: <Platform>_<Kategori>_ddMMMyyyy.xlsx (e.g. Youtube_Kosmetik_08Sep2026.xlsx).
Includes Creator Type, Tier Influencer (Mega/Macro/Micro/Nano), and Affiliate Shop Links in columns.
"""

import os
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd
from database.db_manager import DatabaseManager
from config import EXPORTS_DIR


def clean_category_slug(category: Optional[str]) -> str:
    """Converts category names like 'Kosmetik & Skincare' into clean slug 'kosmetik'."""
    if not category or category.lower() in ["all", "semua", ""]:
        return "all"

    cat_lower = category.lower()
    if "kosmetik" in cat_lower or "beauty" in cat_lower or "skincare" in cat_lower:
        return "kosmetik"
    elif "makan" in cat_lower or "kuliner" in cat_lower or "food" in cat_lower:
        return "makanan"
    elif "fashion" in cat_lower or "outfit" in cat_lower or "ootd" in cat_lower:
        return "fashion"
    elif "gadget" in cat_lower or "tech" in cat_lower or "teknologi" in cat_lower:
        return "gadget"

    clean = re.sub(r'[^a-zA-Z0-9]', '_', cat_lower)
    return re.sub(r'_+', '_', clean).strip('_')


def generate_filename(platform: Optional[str], category: Optional[str], ext: str = "xlsx", has_email_only: bool = False) -> str:
    """Generates standard filename: <Platform>_<Kategori>_ddMMMyyyy.<ext> (e.g. Youtube_Kosmetik_08Sep2026.xlsx)."""
    plat = platform.capitalize() if platform and platform.lower() != "all" else "All"
    cat = clean_category_slug(category).capitalize()
    email_suffix = "_with_email" if has_email_only else ""

    # Membuat format tanggal ddMMMyyyy (contoh: 08Sep2026)
    date_str = datetime.now().strftime("%d%b%Y")

    return f"{plat}_{cat}{email_suffix}_{date_str}.{ext}"


def export_to_excel(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    has_email_only: bool = False,
    creator_type: Optional[str] = None,
    tier: Optional[str] = None,
    min_followers: int = 0,
    filename: Optional[str] = None
) -> str:
    """
    Exports influencers & afiliators to Excel (.xlsx) file with standard name: <Platform>_<Kategori>_ddMMMyyyy.xlsx
    For Google Maps platform, exports business location columns.
    """
    db = DatabaseManager()
    data = db.get_all_influencers(
        platform=platform,
        category=category,
        has_email=has_email_only,
        creator_type=creator_type,
        tier=tier,
        min_followers=min_followers
    )

    if not data:
        return ""

    df = pd.DataFrame(data)

    # Tentukan kolom prioritas berdasarkan platform
    if platform == "google_maps":
        priority_cols = [
            "platform", "channel_title", "address", "lat", "lon",
            "phone_numbers", "custom_url", "emails",
            "category", "search_keyword", "city", "country", "description"
        ]
        column_mapping = {
            "platform": "Platform",
            "channel_title": "Nama Lokasi",
            "address": "Alamat Lengkap",
            "lat": "Latitude",
            "lon": "Longitude",
            "phone_numbers": "No. Telepon",
            "custom_url": "Website",
            "emails": "Email",
            "category": "Kategori",
            "search_keyword": "Kata Kunci Pencarian",
            "city": "Kota",
            "country": "Negara",
            "description": "Deskripsi"
        }
    else:
        priority_cols = [
            "platform", "creator_type", "tier", "channel_title", "handle", "category",
            "city", "estimated_rate_card", "subscribers", "subscribers_formatted",
            "avg_recent_views", "engagement_rate", "emails", "phone_numbers",
            "instagram_handle", "tiktok_handle", "custom_url", "bio_links",
            "affiliate_links", "country"
        ]
        column_mapping = {
            "platform": "Platform",
            "creator_type": "Tipe Akun (Influencer / Afiliator)",
            "tier": "Tier Influencer (PRD: Nano/Micro/Macro/Mega)",
            "channel_title": "Nama Lengkap / Creator",
            "handle": "Username / Handle",
            "category": "Niche / Kategori",
            "city": "Kota / Domisili",
            "estimated_rate_card": "Estimasi Rate Card (Rp)",
            "subscribers": "Followers / Subscribers",
            "subscribers_formatted": "Followers (Teks)",
            "avg_recent_views": "Rata-rata Views",
            "engagement_rate": "Engagement Rate (%)",
            "emails": "Email Bisnis / Endorsement",
            "phone_numbers": "WhatsApp / CP Manager",
            "instagram_handle": "Instagram",
            "tiktok_handle": "TikTok",
            "custom_url": "URL Profil",
            "bio_links": "Linktree / Bio Links",
            "affiliate_links": "Link Shopee / TikTok Affiliate",
            "country": "Negara"
        }
    
    other_cols = [col for col in df.columns if col not in priority_cols]
    final_cols = [col for col in priority_cols if col in df.columns] + other_cols
    df = df[final_cols]

    # Clean header mapping aligned with PRD
    df = df.rename(columns=column_mapping)

    if not filename:
        filename = generate_filename(platform, category, ext="xlsx", has_email_only=has_email_only)

    output_path = os.path.join(EXPORTS_DIR, filename)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Influencer_Afiliator", index=False)

    return output_path


def export_to_csv(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    has_email_only: bool = False,
    creator_type: Optional[str] = None,
    tier: Optional[str] = None,
    min_followers: int = 0,
    filename: Optional[str] = None
) -> str:
    """Exports influencers & afiliators to CSV file."""
    db = DatabaseManager()
    data = db.get_all_influencers(
        platform=platform,
        category=category,
        has_email=has_email_only,
        creator_type=creator_type,
        tier=tier,
        min_followers=min_followers
    )

    if not data:
        return ""

    df = pd.DataFrame(data)

    priority_cols = [
        "platform", "creator_type", "tier", "channel_title", "handle", "category",
        "city", "estimated_rate_card", "subscribers", "subscribers_formatted",
        "avg_recent_views", "engagement_rate", "emails", "phone_numbers",
        "instagram_handle", "tiktok_handle", "custom_url", "bio_links",
        "affiliate_links", "country"
    ]
    other_cols = [col for col in df.columns if col not in priority_cols]
    final_cols = [col for col in priority_cols if col in df.columns] + other_cols
    df = df[final_cols]

    if not filename:
        filename = generate_filename(platform, category, ext="csv", has_email_only=has_email_only)

    output_path = os.path.join(EXPORTS_DIR, filename)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def export_to_json(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    has_email_only: bool = False,
    creator_type: Optional[str] = None,
    tier: Optional[str] = None,
    min_followers: int = 0,
    filename: Optional[str] = None
) -> str:
    """Exports influencer database to JSON format."""
    db = DatabaseManager()
    data = db.get_all_influencers(
        platform=platform,
        category=category,
        has_email=has_email_only,
        creator_type=creator_type,
        tier=tier,
        min_followers=min_followers
    )

    if not data:
        return ""

    if not filename:
        filename = generate_filename(platform, category, ext="json", has_email_only=has_email_only)

    output_path = os.path.join(EXPORTS_DIR, filename)
    df = pd.DataFrame(data)
    df.to_json(output_path, orient="records", indent=2, force_ascii=False)
    return output_path


def export_to_majapahit_laravel(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    min_followers: int = 1000
) -> Dict[str, str]:
    """
    Exports scraped KOL data into MySQL SQL and JSON Seeder
    directly compatible with Laravel 'Majapahit' Agency Database Schema.
    """
    import json
    from parsers.contact_parser import estimate_rate_card

    db = DatabaseManager()
    data = db.get_all_influencers(
        platform=platform,
        category=category,
        min_followers=min_followers
    )

    if not data:
        return {}

    tier_map = {"Nano": 1, "Micro": 2, "Macro": 3, "Mega": 4}

    json_records = []
    sql_statements = [
        "-- Majapahit KOL Agency Database Seeder (Laravel / MySQL)",
        "-- Generated automatically by Multi-Platform KOL Scraper Engine",
        "SET FOREIGN_KEY_CHECKS=0;",
        ""
    ]

    for idx, row in enumerate(data, start=1):
        user_id = idx + 100
        name = row.get("channel_title") or f"Creator {idx}"
        email = row.get("emails").split(",")[0].strip() if row.get("emails") else f"kol_{row.get('handle', '').lstrip('@').lower()}_{idx}@majapahit.agency"
        handle = row.get("handle") or f"@creator_{idx}"
        plat = (row.get("platform") or "instagram").lower()
        tier = row.get("tier") or "Nano"
        tier_id = tier_map.get(tier, 1)
        city = row.get("city") or "Jakarta"
        raw_bio = row.get("description") or ""
        clean_bio = re.sub(r'[\r\n\t]+', ' ', raw_bio).strip()[:400]
        safe_bio_sql = clean_bio.replace("'", "''").replace("\\", "\\\\")
        phone = row.get("phone_numbers").split(",")[0].strip() if row.get("phone_numbers") else ""
        followers = int(row.get("subscribers") or 0)
        er = float(row.get("engagement_rate") or 0.0)
        profile_url = row.get("custom_url") or f"https://{plat}.com/{handle.lstrip('@')}"

        rate_info = estimate_rate_card(plat, followers, tier)
        rates_detail = rate_info.get("rates_detail", {})

        json_item = {
            "user": {
                "name": name,
                "email": email,
                "phone": phone
            },
            "kol_profile": {
                "nickname": name[:50],
                "bio": clean_bio,
                "city": city,
                "tier": tier,
                "status": "aktif",
                "niches": [row.get("category") or "General"]
            },
            "social_media": [
                {
                    "platform": plat,
                    "username": handle,
                    "profile_url": profile_url,
                    "followers_count": followers,
                    "engagement_rate": er
                }
            ],
            "rate_cards": rates_detail
        }
        json_records.append(json_item)

        # SQL generation
        safe_name = name.replace("'", "''").replace("\\", "\\\\")
        safe_email = email.replace("'", "''").replace("\\", "\\\\")
        sql_statements.append(f"-- KOL #{idx}: {safe_name} ({handle})")
        sql_statements.append(f"INSERT INTO users (id, name, email, password, is_active, created_at, updated_at) VALUES ({user_id}, '{safe_name}', '{safe_email}', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 1, NOW(), NOW()) ON DUPLICATE KEY UPDATE name=VALUES(name);")
        sql_statements.append(f"INSERT INTO kol_profiles (user_id, nickname, bio, city, tier_id, status, joined_at, created_at, updated_at) VALUES ({user_id}, '{safe_name[:50]}', '{safe_bio_sql}', '{city}', {tier_id}, 'aktif', NOW(), NOW(), NOW()) ON DUPLICATE KEY UPDATE city=VALUES(city);")
        sql_statements.append(f"INSERT INTO kol_social_media (kol_profile_id, platform, username, profile_url, followers_count, engagement_rate, created_at, updated_at) VALUES ({user_id}, '{plat}', '{handle}', '{profile_url}', {followers}, {er}, NOW(), NOW());")

        for ctype, price in rates_detail.items():
            if isinstance(price, (int, float)):
                sql_statements.append(f"INSERT INTO kol_rate_cards (kol_profile_id, platform, content_type, rate, created_at, updated_at) VALUES ({user_id}, '{plat}', '{ctype}', {price}, NOW(), NOW());")
        sql_statements.append("")

    sql_statements.append("SET FOREIGN_KEY_CHECKS=1;")

    # Save files with date format
    date_str = datetime.now().strftime("%d%b%Y")
    json_path = os.path.join(EXPORTS_DIR, f"majapahit_kol_seed_{date_str}.json")
    sql_path = os.path.join(EXPORTS_DIR, f"majapahit_kol_seed_{date_str}.sql")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_records, f, ensure_ascii=False, indent=2)

    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_statements))

    return {
        "json": json_path,
        "sql": sql_path,
        "count": len(json_records)
    }