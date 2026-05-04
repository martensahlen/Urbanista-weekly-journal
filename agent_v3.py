"""
Urbanista Monday Brief — Agent v3
Every news item now includes a clickable source URL.

Claude's web_search tool returns cited sources — the agent extracts
the real URL for each finding and includes it in the report JSON.

Setup:
  pip install anthropic requests
  export ANTHROPIC_API_KEY=sk-ant-...
  export TEAMS_WEBHOOK_URL=https://prod-xx.logic.azure.com/...

Usage:
  python agent_v3.py --dry-run
  python agent_v3.py
"""

import os, sys, json, datetime, requests, anthropic

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

BRAND_CONTEXT = (
    "Stockholm-based premium consumer audio brand. "
    "Products: over-ear headphones, on-ear headphones, TWS earphones. "
    "Tiers: Essential (~$49), Core (~$99), Signature (~$149+). "
    "Active pipeline: Shibuya (on-ear $49, Aug 2026), Miami 2 (over-ear €149, Oct 2026), "
    "Palo Alto 2 (TWS $99, Jan 2027). Sells in 90+ countries, ~30,000 retail locations. "
    "Key markets: North America, Europe (Nordics, DE, FR, UK), AU/NZ."
)

ITEM_SCHEMA = """{
  "tag": "Region or brand · topic category",
  "headline": "Short punchy headline under 12 words",
  "body": "2-3 sentences. Specific. Include data where available. End with implication.",
  "url": "Full https:// URL to the specific source article or page",
  "source": "Publisher or site name (e.g. 'GfK Insights', 'FCC.gov', 'NothingTech')"
}"""

AI_SECTIONS = {
    "market": {
        "label": "Market Update",
        "emoji": "🌍",
        "prompt": f"""
You are a senior market analyst for Urbanista, a premium audio brand ({BRAND_CONTEXT}).

Search the web for the latest news and data (past 2 weeks) on:
- Consumer audio market trends: TWS, headphones, portable speakers
- Markets: North America, Europe (DE, FR, UK, Nordics), Australia, New Zealand
- Topics: ASP trends, category growth, consumer behaviour, purchase drivers

Find 4 specific, data-driven insights. For each, find and return the real source URL.

Return ONLY a JSON object — no markdown, no preamble:
{{
  "items": [
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA}
  ]
}}
"""
    },
    "product": {
        "label": "Product News",
        "emoji": "🎯",
        "prompt": f"""
You are a competitive intelligence analyst for Urbanista ({BRAND_CONTEXT}).

Search the web for the latest news (past 2 weeks) about these brands:
Nothing, JLab, JBL, Soundcore (Anker), Marshall, Sudio.

Look for: new product launches, pricing, retail expansion, campaigns, sellout signals.
For each finding, return the real URL of the source article or press release.

Return ONLY a JSON object:
{{
  "items": [
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA}
  ]
}}
"""
    },
    "retail": {
        "label": "Retail",
        "emoji": "🏪",
        "prompt": f"""
You are a retail intelligence analyst for Urbanista ({BRAND_CONTEXT}).

Search the web for the latest news (past 2 weeks) about consumer electronics retail:
- Channels: Best Buy, MediaMarkt, Currys, Amazon, Direct-to-consumer (DTC/Shopify), airport retail (duty-free, WHSmith, Heinemann)
- Topics: shelf space changes, category resets, search trends, DTC performance, travel retail

Find 5 specific updates. For each, return the real URL.

Return ONLY a JSON object:
{{
  "items": [
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA}
  ]
}}
"""
    },
    "compliance": {
        "label": "Compliance",
        "emoji": "⚖️",
        "prompt": f"""
You are a regulatory compliance specialist for Urbanista, a consumer audio brand ({BRAND_CONTEXT}).

Search the web for the latest regulatory and compliance news (past 4 weeks) for:
- Markets: EU, US (FCC), UK (UKCA), Canada (ISED), Australia, New Zealand
- Topics: RoHS, REACH, EU Battery Regulation, Radio Equipment Directive,
  FCC Part 15, ICES-003, CE/UKCA marking, SAR limits, packaging regulations

Find 4 relevant updates. For each, return the direct URL to the regulation, notice, or guidance page.

Return ONLY a JSON object:
{{
  "items": [
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA}
  ]
}}
"""
    },
    "ai": {
        "label": "AI Tips & Tricks",
        "emoji": "✦",
        "prompt": f"""
You are an AI adoption specialist writing for Urbanista, a 15-person premium audio brand ({BRAND_CONTEXT}).

Search the web for the latest practical AI use cases, tools, and tips relevant to:
- Small product companies (10–20 people) using AI
- Functions: Finance (FX, reporting), Operations (PO, approvals), Logistics (tracking, emails),
  Sales (pitch decks, CRM, retailer narratives), Product (compliance, brief writing, research)
- Tools: Claude, ChatGPT, Copilot, Zapier, Make, Notion AI, or similar

Find 6 specific, actionable tips. Each must link to a real article, tool page, or case study.
Frame each in terms of what a 15-person brand can do this week — practical, not theoretical.

Return ONLY a JSON object:
{{
  "items": [
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA},
    {ITEM_SCHEMA}
  ]
}}
"""
    }
}

SECTION_META = [
    ("market",     "Market Update",  "🌍", "01"),
    ("product",    "Product News",   "🎯", "02"),
    ("retail",     "Retail",         "🏪", "03"),
    ("compliance", "Compliance",     "⚖️", "04"),
    ("ai",         "AI Tips",        "✦",  "05"),
]

# ─────────────────────────────────────────────────────────────
# AGENT
# ─────────────────────────────────────────────────────────────

def research_section(client, key, section):
    print(f"  → {section['emoji']} Researching {section['label']}...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": section["prompt"]}]
    )
    # Get the last text block (final answer after tool use)
    text_blocks = [b for b in response.content if hasattr(b, "text")]
    raw = text_blocks[-1].text if text_blocks else "{}"
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"    ⚠️  JSON parse failed for {key}, returning empty")
        return {"items": []}


def generate_intro(client, results):
    print("  → ✍️  Writing editorial intro...")
    headlines = [
        item["headline"]
        for key in ["market", "product", "retail"]
        for item in results.get(key, {}).get("items", [])[:1]
    ]
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        messages=[{"role": "user", "content": f"""
Write a 2-sentence editorial intro for Urbanista's Monday Brief.
Tone: sharp, informed, slightly editorial. Like a smart colleague summarising the week.
These are the top stories: {' | '.join(headlines)}
Respond with ONLY the 2-sentence intro. No quotes, no labels.
"""}]
    )
    return response.content[0].text.strip()


def generate_watch_next(client, results):
    print("  → 👀 Generating Watch Next...")
    all_headlines = " | ".join(
        item["headline"]
        for key in results
        for item in results[key].get("items", [])
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=120,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": f"""
Based on these headlines from this week's Urbanista Monday Brief:
{all_headlines}

Search for any upcoming events, earnings calls, deadlines, or launches in the next 7 days
that are relevant to Urbanista (audio industry, retail, compliance).

Write 1-2 sentences on what to watch next week. Be specific — name events and dates.
Respond with ONLY the watch next text.
"""}]
    )
    text_blocks = [b for b in response.content if hasattr(b, "text")]
    return text_blocks[-1].text.strip() if text_blocks else ""


def build_adaptive_card(report, edition, date_str):
    """Teams Adaptive Card with clickable source links per item."""

    def item_blocks(item):
        blocks = [
            {"type": "TextBlock", "text": f"**{item.get('headline', '')}**", "wrap": True, "spacing": "Medium"},
            {"type": "TextBlock", "text": item.get("body", ""), "wrap": True, "isSubtle": True, "size": "Small", "spacing": "Small"},
        ]
        if item.get("url") and item.get("source"):
            blocks.append({
                "type": "TextBlock",
                "text": f"_{item.get('tag', '')}_ · [{item['source']}]({item['url']})",
                "wrap": True, "size": "ExtraSmall", "spacing": "Small",
                "isSubtle": True, "color": "Accent"
            })
        return blocks

    def section_blocks(key, label, emoji, number, data):
        blocks = [
            {
                "type": "TextBlock",
                "text": f"{emoji} {label.upper()} ({number})",
                "weight": "Bolder", "size": "Small",
                "color": "Accent", "spacing": "Large", "separator": True
            }
        ]
        for item in data.get("items", []):
            blocks += item_blocks(item)
        return blocks

    body = [
        {"type": "TextBlock", "text": f"URBANISTA MONDAY BRIEF · {edition}", "weight": "Lighter", "size": "Small", "isSubtle": True},
        {"type": "TextBlock", "text": date_str, "weight": "Lighter", "size": "Small", "isSubtle": True, "spacing": "None"},
        {"type": "TextBlock", "text": report["intro"], "wrap": True, "size": "Medium", "spacing": "Medium", "isSubtle": True}
    ]

    for key, label, emoji, number in SECTION_META:
        body += section_blocks(key, label, emoji, number, report["sections"].get(key, {}))

    body += [
        {"type": "TextBlock", "text": "👀 WATCH NEXT WEEK", "weight": "Bolder", "size": "Small",
         "color": "Warning", "separator": True, "spacing": "Large"},
        {"type": "TextBlock", "text": report["watch_next"], "wrap": True, "isSubtle": True, "size": "Small"},
        {"type": "TextBlock",
         "text": "Urbanista Monday Brief · Every Monday 08:00 CET · 100% AI researched · All sources linked",
         "size": "ExtraSmall", "isSubtle": True, "spacing": "Large", "separator": True}
    ]

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


def post_to_teams(webhook_url, payload):
    print("  → 📨 Posting to Teams...")
    r = requests.post(webhook_url, json=payload,
                      headers={"Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    print(f"  ✓ Posted (HTTP {r.status_code})")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set."); sys.exit(1)

    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
    if not webhook_url and not dry_run:
        print("Error: TEAMS_WEBHOOK_URL not set. Use --dry-run."); sys.exit(1)

    now = datetime.datetime.now()
    date_str = now.strftime("%A, %-d %B %Y")
    edition = f"W{now.isocalendar()[1]} · {now.year}"

    print(f"\n📰 Urbanista Monday Brief — {date_str}")
    print("=" * 52)

    client = anthropic.Anthropic(api_key=api_key)

    print("\n[1/4] Running research passes...")
    results = {}
    for key, section in AI_SECTIONS.items():
        results[key] = research_section(client, key, section)

    print("\n[2/4] Writing intro & watch next...")
    intro = generate_intro(client, results)
    watch_next = generate_watch_next(client, results)

    report = {
        "intro": intro,
        "watch_next": watch_next,
        "sections": results
    }

    print("\n[3/4] Building Adaptive Card...")
    card = build_adaptive_card(report, edition, date_str)

    if dry_run:
        print("\n── DRY RUN ──")
        print(f"\n{intro}\n")
        for key, label, emoji, number in SECTION_META:
            print(f"\n{emoji} {label}")
            for item in results.get(key, {}).get("items", []):
                print(f"  [{item.get('tag','')}] {item.get('headline','')}")
                print(f"  {item.get('body','')}")
                print(f"  🔗 {item.get('source','')} — {item.get('url','')}\n")
        print(f"👀 {watch_next}\n")
    else:
        print("\n[4/4] Posting to Teams...")
        post_to_teams(webhook_url, card)
        print(f"\n✓ Urbanista Monday Brief delivered — {edition}\n")


if __name__ == "__main__":
    main()
