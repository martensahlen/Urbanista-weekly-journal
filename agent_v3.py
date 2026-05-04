"""
Urbanista Monday Brief — Agent
"""

import os, sys, json, datetime, re, requests, anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL = "claude-sonnet-4-6"

SECTIONS = [
    {
        "key": "market",
        "label": "Market Update",
        "emoji": "🌍",
        "prompt": 'Search for recent news about the consumer audio market (headphones, earphones, speakers) in North America and Europe. Find 3 interesting findings. Return ONLY valid JSON in exactly this format, with no other text before or after:\n{"items":[{"tag":"NA","headline":"Battery life now top purchase driver","body":"NPD data shows battery life overtook ANC as the top purchase driver in North America in 2025. Brands leading on endurance messaging are outperforming at retail.","url":"https://www.npd.com","source":"NPD"},{"tag":"EU","headline":"Mid-tier ASP drops 8% in Europe","body":"GfK reports average selling prices in the €79-129 headphone tier fell 8% YoY as Chinese brands expand. Premium segment remains stable.","url":"https://www.gfk.com","source":"GfK"},{"tag":"AU","headline":"Speakers outsell headphones in Australia","body":"Portable Bluetooth speakers grew 14% YoY in Australia while headphone units stayed flat. Outdoor lifestyle is driving the shift.","url":"https://www.gfk.com","source":"GfK AU"}]}'
    },
    {
        "key": "product",
        "label": "Product News",
        "emoji": "🎯",
        "prompt": 'Search for recent news about these audio brands: Nothing, JLab, JBL, Soundcore, Marshall, Sudio. Find 3 notable product or business updates. Return ONLY valid JSON in exactly this format, with no other text before or after:\n{"items":[{"tag":"Nothing","headline":"Nothing Ear 3 sells out in 48h","body":"Nothing sold out its EU stock of the Ear 3 at €129 within 48 hours of launch. The drops model is proving effective at driving urgency.","url":"https://nothing.tech","source":"Nothing Tech"},{"tag":"JBL","headline":"JBL Tour Pro 3 launches at €249","body":"JBL released the Tour Pro 3 with a touchscreen charging case. Heavy retail placement across EU from May 12.","url":"https://www.jbl.com","source":"JBL"},{"tag":"Soundcore","headline":"Liberty 4 Pro at €79 with ANC","body":"Soundcore continues aggressive mid-tier expansion with ANC at €79. Strong Amazon placement is driving high review velocity.","url":"https://www.soundcore.com","source":"Soundcore"}]}'
    },
    {
        "key": "retail",
        "label": "Retail",
        "emoji": "🏪",
        "prompt": 'Search for recent news about consumer electronics retail — Best Buy, MediaMarkt, Amazon audio, DTC trends, airport retail. Find 3 relevant updates. Return ONLY valid JSON in exactly this format, with no other text before or after:\n{"items":[{"tag":"Best Buy","headline":"Best Buy cuts audio floor space 12%","body":"Best Buy reduced audio fixture space in its 2025 reset. Low-ASP SKUs are being delisted first while premium brands hold position.","url":"https://corporate.bestbuy.com","source":"Best Buy"},{"tag":"Amazon","headline":"Premium audio search up 34% on Amazon","body":"Amazon data shows premium audio search terms growing 34% YoY. A+ Content and video are now mandatory for conversion at this tier.","url":"https://www.amazon.com","source":"Amazon"},{"tag":"Airports","headline":"Travel retail pushes premium audio","body":"WHSmith and Heinemann are actively expanding premium audio ranges. High-income travellers are an ideal profile for impulse purchase.","url":"https://www.heinemann.com","source":"Heinemann"}]}'
    },
    {
        "key": "compliance",
        "label": "Compliance",
        "emoji": "⚖️",
        "prompt": 'Search for recent regulatory news for consumer electronics in EU, US, UK, Canada, Australia. Look for FCC notices, battery regulations, CE/UKCA updates. Find 3 updates. Return ONLY valid JSON in exactly this format, with no other text before or after:\n{"items":[{"tag":"EU","headline":"EU Battery Regulation QR labelling from Aug 18","body":"QR codes linking to battery data become mandatory for all portable batteries in the EU from August 18 2025. All active SKUs need updated packaging.","url":"https://eur-lex.europa.eu","source":"EUR-Lex"},{"tag":"US","headline":"FCC proposes tighter RF limits for wearables","body":"A new NPRM would tighten SAR testing for devices worn near the head. Comment period open until July 15 2025.","url":"https://www.fcc.gov","source":"FCC"},{"tag":"Canada","headline":"ICES-003 updated to include TWS devices","body":"ISED Canada revised ICES-003 to explicitly list TWS and wireless headphones. Updated compliance statements required for Canadian market access.","url":"https://www.ic.gc.ca","source":"ISED Canada"}]}'
    },
    {
        "key": "ai",
        "label": "AI Tips & Tricks",
        "emoji": "✦",
        "prompt": 'Search for practical AI tips for small product companies with 10-20 employees. Find 3 actionable use cases for Finance, Operations, Logistics, or Sales using Claude, ChatGPT, Copilot, or Zapier. Return ONLY valid JSON in exactly this format, with no other text before or after:\n{"items":[{"tag":"Finance","headline":"Automate FX exposure summaries from ERP exports","body":"Feed Claude your multi-currency revenue export and ask for a plain-English FX risk summary. Saves 2-3 hours per week with no integration required.","url":"https://www.anthropic.com","source":"Anthropic"},{"tag":"Sales","headline":"Generate retailer pitches in under 60 seconds","body":"Prompt Claude with a retailer profile and your product brief to get a tailored pitch, objection handlers, and talking points instantly.","url":"https://www.anthropic.com","source":"Anthropic"},{"tag":"Operations","headline":"AI purchase order review cuts approval time 60%","body":"Use AI to pre-screen POs against policy rules before human review. Flags duplicates, out-of-policy spend, and pricing anomalies automatically.","url":"https://zapier.com","source":"Zapier"}]}'
    }
]


def research_section(section):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    print(f"  → {section['emoji']} {section['label']}...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": section["prompt"]}]
        )
        # Print all text blocks for debugging
        text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text.strip()]
        print(f"    Got {len(text_blocks)} text blocks")
        for i, text in enumerate(text_blocks):
            print(f"    Block {i}: {text[:200]}")
            # Try to find JSON
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                try:
                    result = json.loads(text[start:end])
                    if result.get("items"):
                        result["items"] = result["items"][:3]
                        print(f"    ✓ {section['label']}: {len(result['items'])} items")
                        return section["key"], result
                except json.JSONDecodeError as e:
                    print(f"    JSON error in block {i}: {e}")
        print(f"    ⚠️  No valid JSON found in any block")
        return section["key"], {"items": []}
    except Exception as e:
        print(f"    ⚠️  Exception: {e}")
        return section["key"], {"items": []}


def build_card(results, date_str, edition):
    body = [
        {"type": "TextBlock", "text": f"URBANISTA MONDAY BRIEF · {edition}",
         "weight": "Bolder", "size": "Medium", "wrap": True},
        {"type": "TextBlock", "text": date_str,
         "isSubtle": True, "size": "Small", "spacing": "None"}
    ]

    for section in SECTIONS:
        items = results.get(section["key"], {}).get("items", [])
        body.append({
            "type": "TextBlock",
            "text": f"{section['emoji']} {section['label'].upper()}",
            "weight": "Bolder", "size": "Small",
            "color": "Accent", "spacing": "Large", "separator": True
        })
        if not items:
            body.append({"type": "TextBlock", "text": "_No updates this week_",
                         "isSubtle": True, "size": "Small"})
            continue
        for item in items:
            body.append({"type": "TextBlock", "text": f"**{item.get('headline','')}**",
                         "wrap": True, "spacing": "Medium"})
            body.append({"type": "TextBlock", "text": item.get("body", ""),
                         "wrap": True, "isSubtle": True, "size": "Small", "spacing": "Small"})
            body.append({"type": "TextBlock",
                         "text": f"_{item.get('tag','')}_ · [{item.get('source','Source')}]({item.get('url','#')})",
                         "wrap": True, "size": "ExtraSmall", "color": "Accent", "spacing": "Small"})

    body.append({"type": "TextBlock",
                 "text": "Urbanista Monday Brief · Every Monday 08:00 CET · 100% AI researched",
                 "size": "ExtraSmall", "isSubtle": True, "spacing": "Large", "separator": True})

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4", "body": body
            }
        }]
    }


def main():
    dry_run = "--dry-run" in sys.argv

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set."); sys.exit(1)
    if not os.environ.get("TEAMS_WEBHOOK_URL") and not dry_run:
        print("Error: TEAMS_WEBHOOK_URL not set."); sys.exit(1)

    now = datetime.datetime.now()
    date_str = now.strftime("%A, %-d %B %Y")
    edition = f"W{now.isocalendar()[1]} · {now.year}"

    print(f"\n📰 Urbanista Monday Brief — {date_str}")
    print("=" * 52)
    print("\n[1/3] Running all sections in parallel...")

    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(research_section, s): s for s in SECTIONS}
        for future in as_completed(futures):
            key, data = future.result()
            results[key] = data

    print("\n[2/3] Building card...")
    card = build_card(results, date_str, edition)

    if dry_run:
        print("\n── DRY RUN ──")
        for section in SECTIONS:
            items = results[section["key"]].get("items", [])
            print(f"\n{section['emoji']} {section['label']} ({len(items)} items)")
            for item in items:
                print(f"  • {item.get('headline','')}")
    else:
        print("\n[3/3] Posting to Teams...")
        r = requests.post(os.environ["TEAMS_WEBHOOK_URL"], json=card,
                          headers={"Content-Type": "application/json"}, timeout=30)
        r.raise_for_status()
        print(f"  ✓ Posted (HTTP {r.status_code})")

    print(f"\n✓ Done — {edition}\n")


if __name__ == "__main__":
    main()
