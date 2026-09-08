"""
Channel & Account Filter Module.
Filters out TV stations, news broadcast networks, government channels, and official corporate brand accounts
so that ONLY real individual creators, influencers, and affiliators are collected.
"""

import re
from typing import Optional

# 1. Exact or Substring Media & TV Channel Names (Indonesian & Global Broadcast)
MEDIA_BLACK_LIST = [
    # TV Stations & News Networks
    "kompas", "tvone", "tv one", "inews", "tribun", "liputan6", "liputan 6",
    "trans7", "trans 7", "transtv", "trans tv", "metrotv", "metro tv", "sctv",
    "rcti", "indosiar", "net.", "netmediatama", "rtv", "antaranews", "antara tv",
    "jawapos", "jawa pos", "detikcom", "detik", "kumparan", "suaradotcom", "suara.com",
    "viva.co.id", "viva news", "beritasatu", "berita satu", "cnbc", "cnn indonesia",
    "narasi newsroom", "narasi", "idn times", "tirto.id", "mata najwa", "pikiran rakyat",
    "grid.id", "kapanlagi", "insertlive", "insert live", "fokus indosiar", "patroli",
    "redaksi trans7", "seputar inews", "buletin inews", "lintas inews", "kabarpagi",
    "tvri", "tvri nasional", "bbc news", "voa indonesia", "dw indonesia", "tempo.co",
    "tribunnews", "tribun network", "kompascom", "kompasiana", "disway",

    # Official E-Commerce & Corporate Brands
    "shopee indonesia", "tokopedia", "lazada indonesia", "blibli", "bukalapak",
    "gojek indonesia", "grab indonesia", "traveloka", "tiket.com", "indomaret",
    "alfamart", "unilever indonesia", "wings group", "nestle indonesia", "indofood",
    "samsung indonesia", "xiaomi indonesia", "oppo indonesia", "vivo indonesia",
    "realme indonesia", "asus indonesia", "lenovo indonesia", "apple indonesia",
    "wardah beauty", "emina cosmetics", "make over", "somethinc official",
    "scarlett whitening", "avoskin", "whitelab", "erha", "garnier indonesia",
    "l'oreal paris", "maybelline indonesia", "ponds indonesia", "nivea indonesia",

    # Government / Institutions / Political
    "kementerian", "kemkominfo", "kemenkes", "kemendikbud", "kemenkeu", "kemenparekraf",
    "dpr ri", "mpr ri", "polri", "tni ad", "humas polri", "pemprov", "pemkab", "pemkot",
    "badan pusat statistik", "bmkg", "bnpb", "kpk", "kejaksaan", "mahkamah agung"
]

# 2. Regex Patterns indicating media/corporate accounts
MEDIA_TITLE_PATTERNS = [
    re.compile(r'\b(news|berita|redaksi|televisi|broadcasting|channel resmi|official channel|breaking news)\b', re.IGNORECASE),
    re.compile(r'\b(tv|newsroom|media)\b', re.IGNORECASE),
    re.compile(r'\b(koran|harian|portal berita|warta)\b', re.IGNORECASE)
]


def is_blacklisted_channel(title: Optional[str], handle: Optional[str] = None, description: Optional[str] = None) -> bool:
    """
    Returns True if the channel is a TV station, news network, government body,
    or official brand corporate account (NOT an individual influencer/afiliator).
    """
    title_clean = (title or "").lower().strip()
    handle_clean = (handle or "").lower().strip().lstrip('@')
    desc_clean = (description or "").lower()

    # 1. Check direct blacklist keywords in title & handle
    for bad_name in MEDIA_BLACK_LIST:
        if bad_name in title_clean or bad_name in handle_clean:
            return True

    # 2. Check title against media patterns
    for pat in MEDIA_TITLE_PATTERNS:
        # Match 'TV' or 'News' in title unless it's a known individual channel name
        if pat.search(title_clean) or pat.search(handle_clean):
            # Allow individual creator exceptions like 'Dhiarcom TV' or 'Tech TV' if they don't have corporate news keywords
            if any(k in title_clean for k in ["berita", "news", "official", "redaksi", "televisi", "kompas", "tribun", "liputan"]):
                return True
            if title_clean.endswith(" tv") or title_clean.endswith(" news") or handle_clean.endswith("tv") or handle_clean.endswith("news"):
                return True

    # 3. Check description indicators for news agencies / television programs
    if any(k in desc_clean for k in [
        "stasiun televisi", "portal berita resmi", "program berita",
        "redaksi berita", "siaran berita", "tayangan berita", "televisi swasta",
        "official youtube channel of", "channel resmi dari pt", "hak cipta milik pt"
    ]):
        return True

    return False
