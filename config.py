"""
Configuration file for Multi-Platform Influencer & Afiliator Scraper (Indonesia).
Features dynamic massive query expansion targeting both Influencers (Endorsements)
and Afiliators (TikTok Affiliate, Shopee Affiliate, Keranjang Kuning, Racun & Spill Produk).
"""

import os
import itertools
from pathlib import Path
from typing import List, Dict

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = os.path.join(BASE_DIR, "data", "influencers.db")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")

# Ensure directories exist
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Default scraping limits
DEFAULT_TARGET_PER_CATEGORY = 100
MAX_RECENT_VIDEOS_ANALYSIS = 10

# Request Headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}


def generate_niche_queries(category: str) -> List[str]:
    """
    Dynamically generates hyper-targeted search queries for both Influencers & Afiliators in Indonesia.
    """
    queries = []
    cat_lower = category.lower()

    # Core actions for both Influencers & Afiliators
    actions = [
        "review", "rekomendasi", "battle", "haul", "tutorial", "racun", "spill",
        "tips", "unboxing", "shopee affiliate", "tiktok affiliate", "spill link",
        "racun shopee", "racun tiktok", "keranjang kuning", "koleksi link"
    ]

    if "kosmetik" in cat_lower or "beauty" in cat_lower or "skincare" in cat_lower:
        items = [
            "skincare", "sunscreen", "serum", "cushion", "toner", "moisturizer", "facial wash",
            "makeup", "lip tint", "lip cream", "bedak", "eyeliner", "mascara", "foundation",
            "retinol", "niacinamide", "salicylic acid", "skincare lokal", "kosmetik lokal",
            "micellar water", "clay mask", "sheet mask", "body lotion pemutih", "parfum lokal",
            "hair care", "eyeshadow", "blush on", "setting spray", "skincare cowok"
        ]
        contexts = [
            "indonesia", "shopee", "tiktok", "kulit berjerawat", "kulit berminyak", "kulit kering",
            "kulit kusam", "pemula", "remaja", "murah", "terbaik", "viral", "cowok",
            "glowing", "bpom", "under 50k", "under 100k", "brand lokal", "affiliate", "spill produk"
        ]
        for a, i in itertools.product(actions, items):
            queries.append(f"{a} {i} indonesia")
        for i, c in itertools.product(items, contexts):
            queries.append(f"{i} {c}")

    elif "makan" in cat_lower or "kuliner" in cat_lower or "food" in cat_lower:
        actions_food = actions + ["kuliner", "street food", "mukbang", "review makanan", "hunting makanan", "resep", "jajanan", "makanan viral"]
        locations = [
            "jakarta", "bandung", "surabaya", "jogja", "semarang", "solo", "malang", "medan",
            "bali", "bogor", "tangerang", "bekasi", "palembang", "makassar", "indonesia"
        ]
        types = [
            "viral", "malam", "pedas", "enak", "murah", "legendaris", "hidden gem", "kaki lima",
            "pasar", "kekinian", "bakso", "mie ayam", "seblak", "nasi goreng", "seafood",
            "sate", "ayam geprek", "dimsum", "cafe aesthetic", "coffee shop", "street food", "snack affiliate"
        ]
        for a, l in itertools.product(actions_food, locations):
            queries.append(f"{a} {l}")
        for l, t in itertools.product(locations, types):
            queries.append(f"kuliner {t} {l}")

    elif "fashion" in cat_lower or "outfit" in cat_lower or "ootd" in cat_lower:
        items = [
            "baju shopee", "outfit kuliah", "fashion hijab", "outfit cowok", "outfit cewek",
            "brand lokal", "sepatu lokal", "tas lokal", "celana kulot", "blazer", "hoodie",
            "thrift shop", "outfit lebaran", "outfit hangout", "outfit kantor", "dress", "outer",
            "sneakers lokal", "kaos distro", "styling outfit", "rekomendasi kemeja", "cardigan"
        ]
        modifiers = ["indonesia", "murah", "aesthetic", "simple", "kekinian", "shopee haul", "lokal", "vintage", "skena", "korean style", "affiliate", "spill link"]
        for a, i in itertools.product(actions, items):
            queries.append(f"{a} {i} indonesia")
        for i, m in itertools.product(items, modifiers):
            queries.append(f"{i} {m}")

    elif "gadget" in cat_lower or "tech" in cat_lower or "teknologi" in cat_lower:
        items = [
            "gadget", "hp murah", "smartphone", "laptop kuliah", "laptop gaming", "tws murah",
            "smartwatch", "iphone bekas", "tablet murah", "rakit pc", "kamera pemula", "hp 2 jutaan",
            "hp 1 jutaan", "hp 3 jutaan", "hp 5 jutaan", "gadget unik", "ipad", "android", "powerbank",
            "mechanical keyboard", "monitor gaming", "headphone bluetooth", "smart home", "aksesoris hp"
        ]
        modifiers = ["indonesia", "terbaik", "murah", "berkualitas", "gaming", "pelajar", "2025", "2026", "worth it", "affiliate", "shopee"]
        for a, i in itertools.product(actions, items):
            queries.append(f"{a} {i} indonesia")
        for i, m in itertools.product(items, modifiers):
            queries.append(f"{i} {m}")

    else:
        queries = [f"{category} indonesia", f"review {category} indonesia", f"affiliate {category} indonesia", f"spill {category}"]

    # Deduplicate while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)

    return unique_queries


# Primary Niche Definitions
NICHES: Dict[str, List[str]] = {
    "Kosmetik & Skincare": generate_niche_queries("Kosmetik & Skincare"),
    "Makanan & Kuliner": generate_niche_queries("Makanan & Kuliner"),
    "Fashion & Outfit": generate_niche_queries("Fashion & Outfit"),
    "Gadget & Teknologi": generate_niche_queries("Gadget & Teknologi")
}
