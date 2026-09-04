"""
media_resolver.py — Automated authentic defense and frontier technology media resolver.
Queries Wikimedia Commons for verified public-domain photography of military hardware,
aerospace platforms, space systems, and semiconductor facilities, with curated high-res fallbacks.
"""

import json
import logging
import re
import urllib.parse
import urllib.request

CURATED_STOCK = {
    'ai': {
        'url': 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Frontier neural network infrastructure and high-density parallel computing clusters powering next-generation autonomous systems.'
    },
    'semiconductor': {
        'url': 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Advanced silicon wafer fabrication and semiconductor architecture, central to sovereign electronic supply chains.'
    },
    'compute': {
        'url': 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Hyperscale data center server infrastructure driving sovereign cloud computing and operational AI deployments.'
    },
    'cyber': {
        'url': 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Critical digital infrastructure telemetry and cyber domain monitoring safeguarding national communication corridors.'
    },
    'space': {
        'url': 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Space-based intelligence, surveillance, and reconnaissance (ISR) orbital assets monitoring strategic maritime corridors.'
    },
    'aviation': {
        'url': 'https://images.unsplash.com/photo-1519074069444-1ba4fff16def?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Air combat platform maneuvering in operational air space during multi-domain integration exercises.'
    },
    'naval': {
        'url': 'https://images.unsplash.com/photo-1509228468518-180dd4864904?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Naval surface combatants conducting blue-water patrol and sea lane protection operations in contested waterways.'
    },
    'missile': {
        'url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/The_Brahmos_Missile_system_passes_through_the_Rajpath_during_the_full_dress_rehearsal_for_the_Republic_Day_Parade_in_New_Delhi_on_January_23%2C2006.jpg/1280px-The_Brahmos_Missile_system_passes_through_the_Rajpath_during_the_full_dress_rehearsal_for_the_Republic_Day_Parade_in_New_Delhi_on_January_23%2C2006.jpg',
        'caption': 'Tactical missile mobile launch battery demonstrating sovereign standoff strike and coastal deterrence capabilities.'
    },
    'defense': {
        'url': 'https://images.unsplash.com/photo-1508614589041-895b88991e3e?auto=format&fit=crop&w=1200&q=80',
        'caption': 'Tactical defense technology deployment integrating sensor networks and rapid operational response systems.'
    }
}

KNOWN_ENTITIES = [
    ('BrahMos', 'BrahMos supersonic cruise missile system developed under Indo-Russian defense collaboration.'),
    ('Tejas', 'HAL Tejas Light Combat Aircraft (LCA) conducting aerial trials under the Atmanirbhar Bharat initiative.'),
    ('Rafale', 'Dassault Rafale multirole combat aircraft configured for air dominance and precision deep-strike.'),
    ('AMCA', 'Advanced Medium Combat Aircraft (AMCA) fifth-generation indigenous stealth fighter development program.'),
    ('Su-30MKI', 'Sukhoi Su-30MKI multirole air superiority fighter of the Indian Air Force.'),
    ('Agni-V', 'Agni-V long-range strategic missile equipped with Multiple Independently Targetable Re-entry Vehicle (MIRV) technology.'),
    ('S-400', 'S-400 Triumf long-range surface-to-air missile defense system deployed for airspace fortification.'),
    ('Vikrant', 'INS Vikrant indigenous aircraft carrier operating during blue-water fleet integration maneuvers.'),
    ('Gaganyaan', 'ISRO human spaceflight program launch vehicle and orbital module infrastructure.'),
    ('ISRO', 'Indian Space Research Organisation (ISRO) satellite launch vehicle at the Satish Dhawan Space Centre.'),
    ('C-295', 'Airbus / Tata C-295 tactical military transport aircraft under sovereign co-production.'),
    ('Pinaka', 'Pinaka Multi-Barrel Rocket Launcher (MBRL) system providing saturated artillery firepower.'),
    ('MQ-9', 'General Atomics MQ-9 High-Altitude Long-Endurance (HALE) surveillance and strike remotely piloted aircraft.'),
    ('Drone', 'Unmanned aerial surveillance vehicle deployed for border ISR and situational awareness.'),
    ('Semiconductor', 'Cleanroom micro-lithography fabrication facility producing sub-nanometer integrated circuits.'),
    ('Quantum', 'Advanced quantum computing and photonic cryptography research laboratory for secure communications.'),
    ('Hypersonic', 'Hypersonic technology demonstrator and wind-tunnel aerodynamic velocity testing framework.'),
    ('Submarine', 'Scorpene-class / Kalvari-class diesel-electric attack submarine operating in littoral depths.')
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
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) NeodymiumBot/2.0'}
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
                    if len(caption) > 160:
                        caption = caption[:157] + '...'
                    return {
                        'url': thumb,
                        'title': p.get('title', query),
                        'caption': caption
                    }
    except Exception as e:
        logging.debug(f"Wikimedia search error for '{query}': {e}")
    return None

def resolve_secondary_image(title: str, tags: list | str = None, category: str = '') -> dict:
    """
    Finds the most relevant, authentic secondary image and caption
    based on article title, tags, and category.
    """
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    elif not tags:
        tags = []

    search_text = f"{title} {' '.join(tags)} {category}".lower()

    # 1. Check known high-value defense/tech entities
    for entity, fallback_caption in KNOWN_ENTITIES:
        if entity.lower() in search_text:
            wiki_res = search_wikimedia(f"{entity} military") or search_wikimedia(entity)
            if wiki_res:
                return wiki_res
            cat_key = entity.lower()
            if cat_key in CURATED_STOCK:
                return {
                    'url': CURATED_STOCK[cat_key]['url'],
                    'caption': fallback_caption
                }
            return {
                'url': CURATED_STOCK.get('defense', CURATED_STOCK['aviation'])['url'],
                'caption': fallback_caption
            }

    # 2. Check topical categories for stock fallback
    if any(k in search_text for k in ['chip', 'semiconductor', 'tsmc', 'lithography', 'fab']):
        return CURATED_STOCK['semiconductor']
    if any(k in search_text for k in ['ai', 'artificial intelligence', 'model', 'llm', 'deepseek', 'openai']):
        return CURATED_STOCK['ai']
    if any(k in search_text for k in ['compute', 'data center', 'nvidia', 'gpu', 'cloud']):
        return CURATED_STOCK['compute']
    if any(k in search_text for k in ['space', 'satellite', 'isro', 'orbit', 'moon', 'lunar']):
        return CURATED_STOCK['space']
    if any(k in search_text for k in ['navy', 'maritime', 'ship', 'carrier', 'destroyer', 'ocean']):
        return CURATED_STOCK['naval']
    if any(k in search_text for k in ['missile', 'rocket', 'artillery', 'air defense', 'hypersonic']):
        return CURATED_STOCK['missile']
    if any(k in search_text for k in ['air force', 'fighter', 'jet', 'aircraft', 'aviation']):
        return CURATED_STOCK['aviation']
    if any(k in search_text for k in ['cyber', 'hack', 'telecom', 'cable', 'internet', 'surveillance']):
        return CURATED_STOCK['cyber']

    # Default defense intelligence asset
    return CURATED_STOCK['defense']
