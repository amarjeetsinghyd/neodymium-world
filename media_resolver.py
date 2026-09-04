"""
media_resolver.py — High-precision defense, aerospace, and tech media resolver.
Uses strict word boundary matching, direct platform Wikipedia queries, and verified stock imagery.
"""

import json
import logging
import re
import urllib.parse
import urllib.request

CURATED_STOCK = {
    'ai': {
        'url': 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80',
        'caption': 'High-density GPU computing clusters and enterprise server architecture accelerating autonomous and frontier intelligence systems.'
    },
    'semiconductor': {
        'url': 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Silicon wafer micro-lithography and advanced semiconductor fabrication, essential to sovereign electronics resilience.'
    },
    'compute': {
        'url': 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Hyperscale data center server infrastructure driving sovereign compute capacity and real-time operational processing.'
    },
    'cyber': {
        'url': 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Critical digital infrastructure and cyber warfare monitoring operations safeguarding sovereign telemetry.'
    },
    'space': {
        'url': 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Orbital space infrastructure and satellite surveillance constellations monitoring strategic maritime and land corridors.'
    },
    'aviation': {
        'url': 'https://images.unsplash.com/photo-1519074069444-1ba4fff16def?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Frontline supersonic combat aircraft executing tactical air dominance and airspace protection maneuvers.'
    },
    'naval': {
        'url': 'https://images.unsplash.com/photo-1509228468518-180dd4864904?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Blue-water surface combatants operating in contested sea lanes to preserve maritime trade security.'
    },
    'missile': {
        'url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/The_Brahmos_Missile_system_passes_through_the_Rajpath_during_the_full_dress_rehearsal_for_the_Republic_Day_Parade_in_New_Delhi_on_January_23%2C2006.jpg/1280px-The_Brahmos_Missile_system_passes_through_the_Rajpath_during_the_full_dress_rehearsal_for_the_Republic_Day_Parade_in_New_Delhi_on_January_23%2C2006.jpg',
        'caption': 'Surface-to-air and tactical missile battery maintaining high-readiness airspace defense and standoff deterrence.'
    },
    'drone': {
        'url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/MQ-9_Reaper_UAV_%28cropped%29.jpg/1280px-MQ-9_Reaper_UAV_%28cropped%29.jpg',
        'caption': 'Medium and high-altitude unmanned aerial surveillance vehicle deployed for persistent border ISR and reconnaissance.'
    },
    'defense': {
        'url': 'https://images.unsplash.com/photo-1508614589041-895b88991e3e?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Integrated tactical defense systems, radar sensor arrays, and rapid-response military readiness network.'
    }
}

# (Regex pattern, Wikipedia Query, Fallback Caption, Category Key)
KNOWN_PLATFORMS = [
    (r'\bQRSAM\b', 'QRSAM', 'Quick Reaction Surface-to-Air Missile (QRSAM) developed by DRDO for tactical battlefield airspace defense.', 'missile'),
    (r'\bAkash\b', 'Akash missile', 'Akash surface-to-air missile defense battery providing medium-range air interception.', 'missile'),
    (r'\bAstra\b', 'Astra missile', 'Astra beyond-visual-range air-to-air missile integrated onto frontline combat aircraft.', 'missile'),
    (r'\bBrahMos\b', 'BrahMos', 'BrahMos supersonic cruise missile mobile autonomous launcher deployed for precision standoff strike.', 'missile'),
    (r'\bAgni\b', 'Agni-V', 'Agni-V long-range strategic ballistic missile equipped with MIRV warhead capability.', 'missile'),
    (r'\bS-400\b', 'S-400 missile system', 'S-400 Triumf long-range surface-to-air air defense system deployed for strategic airspace protection.', 'missile'),
    (r'\bPinaka\b', 'Pinaka multi-barrel rocket launcher', 'Pinaka Multi-Barrel Rocket Launcher (MBRL) providing rapid concentrated artillery fire.', 'missile'),
    (r'\b(ERFB|artillery|howitzer|shells)\b', 'ATAGS artillery', 'Advanced artillery gun systems and extended-range full-bore munitions providing standoff firepower.', 'defense'),
    (r'\b(Tejas|LCA)\b', 'HAL Tejas', 'HAL Tejas Light Combat Aircraft operating in air dominance and precision strike configurations.', 'aviation'),
    (r'\bAMCA\b', 'Advanced Medium Combat Aircraft', 'Advanced Medium Combat Aircraft (AMCA) fifth-generation indigenous stealth fighter program.', 'aviation'),
    (r'\b(Su-30|Su-30MKI|Sukhoi)\b', 'Sukhoi Su-30MKI', 'Sukhoi Su-30MKI multirole air superiority fighter of the Indian Air Force.', 'aviation'),
    (r'\bRafale\b', 'Dassault Rafale', 'Dassault Rafale multirole omnirole combat aircraft configured for long-range precision strike.', 'aviation'),
    (r'\bC-295\b', 'Airbus C295', 'Airbus / Tata C-295 tactical military transport aircraft under sovereign co-production.', 'aviation'),
    (r'\b(Vikrant|aircraft carrier)\b', 'INS Vikrant (2013)', 'INS Vikrant indigenous aircraft carrier conducting blue-water naval flight operations.', 'naval'),
    (r'\b(submarine|Kalvari|Scorpene)\b', 'Kalvari-class submarine', 'Kalvari-class diesel-electric attack submarine conducting subsurface patrol operations.', 'naval'),
    (r'\b(warship|frigate|destroyer)\b', 'Visakhapatnam-class destroyer', 'Stealth guided missile destroyer conducting maritime surveillance and deterrence in blue waters.', 'naval'),
    (r'\b(Bhargavastra|C-UAS|counter-drone|anti-drone)\b', 'Counter unmanned air system', 'Counter-UAS kinetic and electronic air defense suite protecting critical military installations.', 'drone'),
    (r'\b(drone|swarms?|UAV|loitering)\b', 'General Atomics MQ-9 Reaper', 'Unmanned aerial surveillance and autonomous tactical drone system operating on operational borders.', 'drone'),
    (r'\b(Starship|SpaceX)\b', 'SpaceX Starship', 'SpaceX Starship orbital launch vehicle demonstrating heavy-lift space transport capabilities.', 'space'),
    (r'\b(Gaganyaan|ISRO|satellite|orbital)\b', 'Gaganyaan', 'ISRO human spaceflight program launch platform and orbital mission infrastructure.', 'space'),
    (r'\b(semiconductor|chips?|fab|lithography|TSMC)\b', 'Semiconductor device fabrication', 'Advanced cleanroom silicon micro-lithography fabrication facility producing sovereign integrated circuits.', 'semiconductor'),
    (r'\bquantum\b', 'Quantum computer', 'Advanced quantum computing and photonic laboratory researching cryptographic resilience.', 'compute'),
    (r'\bhypersonic\b', 'Hypersonic weapon', 'Hypersonic glide technology demonstrator testing extreme aerodynamic boundary layer thermal shields.', 'missile'),
    (r'\b(air defense|surface-to-air|SAM)\b', 'Surface-to-air missile', 'Tactical air defense missile battery providing multi-tiered airspace interception.', 'missile')
]

BROAD_TOPICS = [
    (r'\b(missiles?|rockets?|artillery|ammunition|warheads?|torpedo)\b', 'missile'),
    (r'\b(fighter|jets?|aircraft|aviation|air force|iaf)\b', 'aviation'),
    (r'\b(naval|navy|ships?|vessels?|maritime|sea|ocean)\b', 'naval'),
    (r'\b(space|satellites?|isro|nasa|lunar|orbit)\b', 'space'),
    (r'\b(drones?|uav|unmanned|c-uas|autonomous)\b', 'drone'),
    (r'\b(semiconductors?|chips?|lithography|microelectronics)\b', 'semiconductor'),
    (r'\b(supercomputers?|data centers?|servers?|cloud|gpus?)\b', 'compute'),
    (r'\b(cyber|encryption|hacking|telecom|cables?|telemetry)\b', 'cyber'),
    (r'\b(ai|artificial intelligence|machine learning|llm|deepseek|openai|anthropic|chatgpt)\b', 'ai'),
    (r'\b(defense|defence|military|army|drdo|deterrence|border|lac)\b', 'defense'),
]

def search_wikimedia(query: str) -> dict | None:
    """Queries Wikimedia Commons API for a verified high-resolution photograph."""
    try:
        url = (
            f"https://en.wikipedia.org/w/api.php?action=query&format=json"
            f"&prop=pageimages|extracts&generator=search"
            f"&gsrsearch={urllib.parse.quote(query)}"
            f"&pithumbsize=1200&exintro=1&explaintext=1&exsentences=1"
        )
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) NeodymiumBot/3.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            pages = list(data.get('query', {}).get('pages', {}).values())
            pages.sort(key=lambda x: x.get('index', 99))
            for p in pages:
                thumb = p.get('thumbnail', {}).get('source', '')
                clean_url = thumb.split('?')[0].lower()
                # Ensure we only pick real photographs, never SVG diagrams or corporate logos
                if (
                    clean_url
                    and any(clean_url.endswith(ext) for ext in ('.jpg', '.jpeg', '.webp', '.png'))
                    and '.svg' not in clean_url
                    and 'logo' not in clean_url
                    and 'icon' not in clean_url
                    and 'flag' not in clean_url
                ):
                    raw_caption = p.get('extract') or p.get('title', query)
                    caption = re.sub(r'\[.*?\]', '', raw_caption).strip()
                    # Clean any non-printable/exotic IPA characters
                    caption = caption.encode('ascii', 'ignore').decode('ascii')
                    if len(caption) > 160:
                        caption = caption[:157] + '...'
                    return {
                        'url': thumb,
                        'title': p.get('title', query),
                        'caption': caption if caption else query
                    }
    except Exception as e:
        logging.debug(f"Wikimedia search error for '{query}': {e}")
    return None

def resolve_secondary_image(title: str, tags: list | str = None, category: str = '') -> dict:
    """
    Finds the most relevant, authentic secondary image and caption
    based on article title, tags, and category using strict word boundary matching.
    """
    if isinstance(tags, str):
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    elif isinstance(tags, list):
        tag_list = [str(t).strip() for t in tags if str(t).strip()]
    else:
        tag_list = []

    full_context = f"{title} {' '.join(tag_list)} {category}"

    # 1. Check known specific platforms with word-boundary regex
    for pattern, wiki_query, fallback_caption, cat_key in KNOWN_PLATFORMS:
        if re.search(pattern, full_context, re.IGNORECASE):
            wiki_res = search_wikimedia(wiki_query)
            if wiki_res and wiki_res.get('caption'):
                return wiki_res
            # Use specific category fallback with authentic platform caption
            stock = CURATED_STOCK.get(cat_key, CURATED_STOCK['defense']).copy()
            stock['caption'] = fallback_caption
            return stock

    # 2. Check broad domain categories with strict word-boundary regex
    for pattern, cat_key in BROAD_TOPICS:
        if re.search(pattern, full_context, re.IGNORECASE):
            return CURATED_STOCK.get(cat_key, CURATED_STOCK['defense'])

    # 3. Default defense intelligence asset
    return CURATED_STOCK['defense']
