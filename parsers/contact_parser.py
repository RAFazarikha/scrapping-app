"""
Contact & Affiliate Parser Module for Influencer & Afiliator Descriptions & Texts.
Extracts Business Emails, Indonesian WhatsApp/Phones, Instagram, TikTok,
Linktree profiles, Shopee/TikTok Affiliate links, and automatically classifies Creator Type.
"""

import re
from typing import Dict, List, Set, Optional, Any

# Regular Expressions
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    re.IGNORECASE
)

ID_PHONE_REGEX = re.compile(
    r'(?:(?:\+?62)|0)8[1-9][0-9\-.\s]{7,12}\b'
)

WA_LINK_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:api\.whatsapp\.com/send\?phone=|wa\.me/|wa\.link/)([0-9+]+)',
    re.IGNORECASE
)

INSTAGRAM_LINK_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?',
    re.IGNORECASE
)
INSTAGRAM_TEXT_REGEX = re.compile(
    r'(?:ig|instagram|insta)\s*[:=\-]?\s*@?([A-Za-z0-9_.]{3,30})\b',
    re.IGNORECASE
)

TIKTOK_LINK_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?tiktok\.com/@?([A-Za-z0-9_.]+)/?',
    re.IGNORECASE
)
TIKTOK_TEXT_REGEX = re.compile(
    r'(?:tiktok|tt)\s*[:=\-]?\s*@?([A-Za-z0-9_.]{3,30})\b',
    re.IGNORECASE
)

LINKTREE_REGEX = re.compile(
    r'https?://(?:www\.)?(?:linktr\.ee|beacons\.ai|desty\.page|biolinky\.co|msha\.ke|campsite\.bio|lynk\.id)/[A-Za-z0-9_.-]+',
    re.IGNORECASE
)

AFFILIATE_LINK_REGEX = re.compile(
    r'https?://(?:www\.)?(?:shope\.ee|s\.shopee\.co\.id|tokopedia\.link|vt\.tiktok\.com|shopee\.co\.id/universal-link/[A-Za-z0-9_.-]+)/[A-Za-z0-9_.-]+',
    re.IGNORECASE
)

# Affiliate & Endorsement Keyword Classifiers
AFFILIATE_KEYWORDS = [
    "affiliate", "afiliasi", "afiliator", "racun", "spill", "keranjang kuning", "shopeehaul",
    "shope.ee", "koleksi link", "link produk", "racun shopee", "racun tiktok", "komisi",
    "haul", "cek link no", "beli disini", "link di bio no", "shopee.co.id", "tokopedia.link",
    "racunskincare", "spillbaju", "racungadget", "spillproduk"
]

ENDORSEMENT_KEYWORDS = [
    "endorse", "endorsement", "business inquiry", "inquiries", "cp management", "partnership",
    "collaboration", "kerjasama", "collab", "contact business", "pr package", "rate card",
    "brand ambassador", "paid partnership", "sponsored"
]

IGNORED_EMAIL_DOMAINS = {
    "youtube.com", "google.com", "googlegroups.com", "example.com", "domain.com", "email.com"
}
IGNORED_EMAIL_PREFIXES = {
    "support", "help", "noreply", "no-reply", "info@youtube.com", "copyright"
}


# Indonesian Major Cities for Domicile Extraction
INDONESIAN_CITIES = [
    "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang", "Yogyakarta", "Jogja",
    "Solo", "Surakarta", "Malang", "Bali", "Denpasar", "Makassar", "Bogor",
    "Depok", "Tangerang", "Bekasi", "Palembang", "Bandar Lampung", "Batam",
    "Pekanbaru", "Banjarmasin", "Samarinda", "Pontianak", "Manado", "Padang",
    "Cirebon", "Sukabumi", "Tasikmalaya", "Jember", "Kediri", "Madiun"
]


def extract_city(text: str) -> str:
    """Extracts Indonesian city / domicile from bio and description text."""
    if not text:
        return "Indonesia"
    text_clean = f" {text.lower()} "
    for city in INDONESIAN_CITIES:
        pattern = r'\b' + re.escape(city.lower()) + r'\b'
        if re.search(pattern, text_clean):
            return "Yogyakarta" if city.lower() in ["jogja", "yogyakarta"] else city
    return "Indonesia"


def get_influencer_tier(followers: int) -> str:
    """
    Classifies influencer into PRD-compliant agency tiers:
    - Nano: 1,000 - 10,000 followers
    - Micro: 10,000 - 100,000 followers
    - Macro: 100,000 - 1,000,000 followers
    - Mega: > 1,000,000 followers
    """
    if not followers or followers < 1000:
        return "Beginner (<1K)"
    elif followers < 10_000:
        return "Nano"
    elif followers < 100_000:
        return "Micro"
    elif followers < 1_000_000:
        return "Macro"
    else:
        return "Mega"


def estimate_rate_card(platform: str, followers: int, tier: Optional[str] = None) -> Dict[str, Any]:
    """
    Estimates market rate card (in IDR / Rp) for Agency Endorsements based on platform and tier.
    """
    if not tier or tier == "Beginner (<1K)":
        tier = get_influencer_tier(followers)

    plat = (platform or "instagram").lower()

    if tier == "Nano":
        rates = {
            "instagram": {"feed": 500_000, "story": 250_000, "reels": 750_000, "range": "Rp 250.000 - Rp 750.000"},
            "tiktok": {"video": 600_000, "live_hourly": 300_000, "range": "Rp 300.000 - Rp 600.000"},
            "youtube": {"dedicated": 1_500_000, "integration": 750_000, "shorts": 500_000, "range": "Rp 500.000 - Rp 1.500.000"}
        }
    elif tier == "Micro":
        rates = {
            "instagram": {"feed": 2_500_000, "story": 1_000_000, "reels": 3_500_000, "range": "Rp 1.000.000 - Rp 3.500.000"},
            "tiktok": {"video": 3_000_000, "live_hourly": 1_500_000, "range": "Rp 1.500.000 - Rp 3.000.000"},
            "youtube": {"dedicated": 6_000_000, "integration": 3_000_000, "shorts": 2_000_000, "range": "Rp 2.000.000 - Rp 6.000.000"}
        }
    elif tier == "Macro":
        rates = {
            "instagram": {"feed": 10_000_000, "story": 4_000_000, "reels": 15_000_000, "range": "Rp 4.000.000 - Rp 15.000.000"},
            "tiktok": {"video": 12_000_000, "live_hourly": 5_000_000, "range": "Rp 5.000.000 - Rp 12.000.000"},
            "youtube": {"dedicated": 25_000_000, "integration": 12_000_000, "shorts": 7_500_000, "range": "Rp 7.500.000 - Rp 25.000.000"}
        }
    elif tier == "Mega":
        rates = {
            "instagram": {"feed": 30_000_000, "story": 12_000_000, "reels": 40_000_000, "range": "Rp 12.000.000 - Rp 40.000.000+"},
            "tiktok": {"video": 35_000_000, "live_hourly": 15_000_000, "range": "Rp 15.000.000 - Rp 35.000.000+"},
            "youtube": {"dedicated": 60_000_000, "integration": 30_000_000, "shorts": 18_000_000, "range": "Rp 18.000.000 - Rp 60.000.000+"}
        }
    else:
        rates = {
            "instagram": {"feed": 150_000, "story": 75_000, "reels": 200_000, "range": "< Rp 200.000"},
            "tiktok": {"video": 150_000, "live_hourly": 75_000, "range": "< Rp 200.000"},
            "youtube": {"dedicated": 300_000, "integration": 150_000, "shorts": 100_000, "range": "< Rp 300.000"}
        }

    selected = rates.get(plat, rates["instagram"])
    return {
        "tier": tier,
        "platform": plat,
        "estimated_rate_range": selected.get("range", ""),
        "rates_detail": selected
    }


def normalize_indonesian_phone(raw_phone: str) -> Optional[str]:
    """Cleans and formats phone number to standard +628... format."""
    digits = re.sub(r'\D', '', raw_phone)
    if digits.startswith('08'):
        return '+62' + digits[1:]
    elif digits.startswith('628'):
        return '+' + digits
    elif digits.startswith('8') and len(digits) >= 9:
        return '+62' + digits
    elif digits.startswith('6208'):
        return '+62' + digits[3:]
    return None


def extract_emails(text: str) -> List[str]:
    """Extracts valid business emails from text."""
    if not text:
        return []
    
    matches = EMAIL_REGEX.findall(text)
    valid_emails: Set[str] = set()

    for email in matches:
        email_clean = email.strip().lower()
        if re.search(r'\.(png|jpg|jpeg|gif|webp|svg|pdf|mp4|zip)$', email_clean):
            continue
        parts = email_clean.split('@')
        if len(parts) != 2:
            continue
        username, domain = parts
        if domain in IGNORED_EMAIL_DOMAINS:
            continue
        if any(email_clean.startswith(prefix) for prefix in IGNORED_EMAIL_PREFIXES):
            continue
        valid_emails.add(email_clean)

    return sorted(list(valid_emails))


def extract_phones(text: str) -> List[str]:
    """Extracts valid Indonesian WhatsApp/phone numbers from text."""
    if not text:
        return []
    
    found_phones: Set[str] = set()
    wa_matches = WA_LINK_REGEX.findall(text)
    for wa in wa_matches:
        normalized = normalize_indonesian_phone(wa)
        if normalized:
            found_phones.add(normalized)

    phone_matches = ID_PHONE_REGEX.findall(text)
    for p in phone_matches:
        normalized = normalize_indonesian_phone(p)
        if normalized and 11 <= len(normalized) <= 16:
            found_phones.add(normalized)

    return sorted(list(found_phones))


INVALID_HANDLES = {
    "p", "reel", "reels", "stories", "story", "explore", "tv", "channel", "account",
    "accounts", "direct", "business", "inquiry", "inquiries", "contact", "official",
    "admin", "endorse", "endorsement", "partnership", "gmail", "yahoo", "link",
    "klik", "cek", "info", "dan", "atau", "ke", "di", "dari", "pada", "untuk",
    "ini", "itu", "first", "empt", "subscribe", "subscribers", "video", "videos",
    "youtube", "tiktok", "instagram", "facebook", "twitter", "wa", "whatsapp",
    "shopee", "tokopedia", "lazada", "review", "haul", "spill", "racun", "disini"
}


def extract_instagram(text: str) -> Optional[str]:
    """Extracts Instagram username from text or links."""
    if not text:
        return None
    link_match = INSTAGRAM_LINK_REGEX.search(text)
    if link_match:
        handle = link_match.group(1).strip().rstrip('/')
        if handle.lower() not in INVALID_HANDLES and len(handle) >= 3:
            return f"@{handle.lstrip('@')}"

    text_match = INSTAGRAM_TEXT_REGEX.search(text)
    if text_match:
        handle = text_match.group(1).strip()
        if handle.lower() not in INVALID_HANDLES and len(handle) >= 3:
            return f"@{handle.lstrip('@')}"

    return None


def extract_tiktok(text: str) -> Optional[str]:
    """Extracts TikTok username from text or links."""
    if not text:
        return None
    link_match = TIKTOK_LINK_REGEX.search(text)
    if link_match:
        handle = link_match.group(1).strip().rstrip('/')
        if handle.lower() not in INVALID_HANDLES and len(handle) >= 3:
            return f"@{handle.lstrip('@')}"

    text_match = TIKTOK_TEXT_REGEX.search(text)
    if text_match:
        handle = text_match.group(1).strip()
        if handle.lower() not in INVALID_HANDLES and len(handle) >= 3:
            return f"@{handle.lstrip('@')}"

    return None


def extract_linktree_links(text: str) -> List[str]:
    """Extracts link aggregator links (Linktree, Beacons, Desty, Lynk.id, etc.)."""
    if not text:
        return []
    matches = LINKTREE_REGEX.findall(text)
    return sorted(list(set(matches)))


def extract_affiliate_links(text: str) -> List[str]:
    """Extracts Shopee / Tokopedia / TikTok Shop direct affiliate links."""
    if not text:
        return []
    matches = AFFILIATE_LINK_REGEX.findall(text)
    return sorted(list(set(matches)))


def detect_creator_type(text: str, emails: List[str], phones: List[str], affiliate_links: List[str]) -> str:
    """
    Classifies creator as:
    - 'Influencer & Afiliator' (Has both endorsement contacts & affiliate signals)
    - 'Afiliator' (Focuses heavily on affiliate links / racun / spill / keranjang kuning)
    - 'Influencer' (Focuses primarily on sponsorships / endorsement inquiries)
    """
    text_lower = (text or "").lower()
    
    has_affiliate_signal = bool(affiliate_links) or any(k in text_lower for k in AFFILIATE_KEYWORDS)
    has_endorse_signal = bool(emails) or bool(phones) or any(k in text_lower for k in ENDORSEMENT_KEYWORDS)

    if has_affiliate_signal and has_endorse_signal:
        return "Influencer & Afiliator"
    elif has_affiliate_signal:
        return "Afiliator"
    elif has_endorse_signal:
        return "Influencer"
    else:
        return "Influencer & Afiliator"


def extract_all_contacts(text: str, links: Optional[List[str]] = None) -> Dict[str, any]:
    """
    Comprehensive contact & affiliate extraction.
    Returns emails, phones, instagram, tiktok, bio links, affiliate links, and creator type.
    """
    full_text = text or ""
    if links:
        full_text += "\n" + "\n".join(links)

    emails = extract_emails(full_text)
    phones = extract_phones(full_text)
    instagram = extract_instagram(full_text)
    tiktok = extract_tiktok(full_text)
    aggregator_links = extract_linktree_links(full_text)
    affiliate_links = extract_affiliate_links(full_text)
    
    creator_type = detect_creator_type(full_text, emails, phones, affiliate_links)
    city = extract_city(full_text)

    return {
        "emails": emails,
        "emails_str": ", ".join(emails) if emails else "",
        "phones": phones,
        "phones_str": ", ".join(phones) if phones else "",
        "instagram": instagram or "",
        "tiktok": tiktok or "",
        "aggregator_links": aggregator_links,
        "aggregator_links_str": ", ".join(aggregator_links) if aggregator_links else "",
        "affiliate_links": affiliate_links,
        "affiliate_links_str": ", ".join(affiliate_links) if affiliate_links else "",
        "creator_type": creator_type,
        "city": city
    }
