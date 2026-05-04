"""
Urbanista Monday Brief — Final Agent
Simplified prompts and robust JSON extraction for reliable weekly posting.

Setup:
  pip install anthropic requests
  export ANTHROPIC_API_KEY=sk-ant-...
  export TEAMS_WEBHOOK_URL=https://prod-xx.logic.azure.com/...

Usage:
  python agent_final.py --dry-run
  python agent_final.py
"""

import os, sys, json, datetime, re, requests, anthropic

MODEL = "claude-sonnet-4-5"

SECTIONS = [
    {
        "key": "market",
        "label": "Market Update",
        "emoji": "🌍",
        "prompt": """Search the web for the latest news (past 2 weeks) about the consumer audio market — TWS earphones, headphones, and portable speakers — in North America, Europe, UK, Australia, and New Zealand. Find 3 interesting findings about market trends, consumer behaviour, pricing, or category growth.

Respond with ONLY this JSON, nothing else:
{"items":[{"tag":"Region","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Region","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Region","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"}]}"""
    },
    {
        "key": "product",
        "label": "Product News",
        "emoji": "🎯",
        "prompt": """Search the web for the latest news (past 2 weeks) about these audio brands: Nothing, JLab, JBL, Soundcore, Marshall, Sudio. Find 3 notable updates — new products, pricing, campaigns, or retail moves.

Respond with ONLY this JSON, nothing else:
{"items":[{"tag":"Brand","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Brand","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Brand","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"}]}"""
    },
    {
        "key": "retail",
        "label": "Retail",
        "emoji": "🏪",
        "prompt": """Search the web for the latest news (past 2 weeks) about consumer electronics retail — covering Best Buy, MediaMarkt, Currys, Amazon audio category, direct-to-consumer trends, and airport/travel retail. Find 3 relevant updates.

Respond with ONLY this JSON, nothing else:
{"items":[{"tag":"Retailer","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Retailer","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Retailer","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"}]}"""
    },
    {
        "key": "compliance",
        "label": "Compliance",
        "emoji": "⚖️",
        "prompt": """Search the web for the latest regulatory and compliance news (past 4 weeks) relevant to consumer electronics and wireless audio devices in EU, US, UK, Canada, Australia, and New Zealand. Look for new directives, FCC notices, certification updates, battery regulations, labelling requirements. Find 3 updates.

Respond with ONLY this JSON, nothing else:
{"items":[{"tag":"Market","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Market","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Market","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"}]}"""
    },
    {
        "key": "ai",
        "label": "AI Tips & Tricks",
        "emoji": "✦",
        "prompt": """Search the web for practical AI tips for small product companies (10-20 people). Find 3 specific, actionable AI use cases for functions like Finance, Operations, Logistics, Sales, or Product — tools like Claude, ChatGPT, Copilot, Zapier, or Notion AI. Each tip should be something a small team can act on this week.

Respond with ONLY this JSON, nothing else:
{"items":[{"tag":"Function","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Function","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"},{"tag":"Function","headline":"headline here","body":"2 sentences here.","url":"https://source-url.com","source":"Source Name"}]}"""
    }
]


def extract_json(text):
    """Robustly extract JSON from Claude's response."""
    # Strip markdown fences
    text = re.sub(r'```json|```', '', text).strip()
    # Find first { to last }
    start = text.find('{')
    end = text.rfind('}') + 1
    if start >= 0 and end > start:
        candidate = text[start:end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # Try finding items array directly
    match = re.search(r'\{.*?"items".*?\].*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def research_section(client, section):
    print(f"  → {section['emoji']} {section['label']}...")
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": section["prompt"]}]
            )
            # Get all text blocks, try each one
            text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text.strip()]
            for text in reversed(text_blocks):  # try last block first
                result = extract_json(text)
                if result and result.get("items"):
                    print(f"    ✓ {len(result['items'])} items")
                    return result
            print(f"    ⚠️  No valid JSON found (attempt {attempt+1})")
        except Exception as e:
            print(f"    ⚠️  Error (attempt {attempt+1}): {e}")
    return {"items": []}


def build_card(sections_data, date_str, edition):
    body = [
        {
            "type": "TextBlock",
            "text": f"URBANISTA MONDAY BRIEF · {edition}",
            "weight": "Bolder", "size": "Medium", "wrap": True
        },
        {
            "type": "TextBlock",
            "text": date_str,
            "isSubtle": True, "size": "Small", "spacing": "None"
        }
    ]

    for section in SECTIONS:
        data = sections_data.get(section["key"], {})
        items = data.get("items", [])

        body.append({
            "type": "TextBlock",
            "text": f"{section['emoji']} {section['label'].upper()}",
            "weight": "Bolder", "size": "Small",
            "color": "Accent", "spacing": "Large", "separator": True
        })

        if not items:
            body.append({
                "type": "TextBlock",
                "text": "_No updates this week_",
                "isSubtle": True, "size": "Small"
            })
            continue

        for item in items:
            body.append({
                "type": "TextBlock",
                "text": f"**{item.get('headline', '')}**",
                "wrap": True, "spacing": "Medium"
            })
            body.append({
                "type": "TextBlock",
                "text": item.get("body", ""),
                "wrap": True, "isSubtle": True, "size": "Small", "spacing": "Small"
            })
            source_text = f"_{item.get('tag', '')}_ · [{item.get('source', 'Source')}]({item.get('url', '#')})"
            body.append({
                "type": "TextBlock",
                "text": source_text,
                "wrap": True, "size": "ExtraSmall",
                "color": "Accent", "spacing": "Small"
            })

    body.append({
        "type": "TextBlock",
        "text": "Urbanista Monday Brief · Every Monday 08:00 CET · 100% AI researched",
        "size": "ExtraSmall", "isSubtle": True,
        "spacing": "Large", "separator": True
    })

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4",
                "body": body
            }
        }]
    }


def post_to_teams(webhook_url, payload):
    print("  → Posting to Teams...")
    r = requests.post(
        webhook_url, json=payload,
        headers={"Content-Type": "application/json"}, timeout=30
    )
    r.raise_for_status()
    print(f"  ✓ Posted (HTTP {r.status_code})")


def main():
    dry_run = "--dry-run" in sys.argv

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
    print(f"\n[1/3] Running research passes...")

    client = anthropic.Anthropic(api_key=api_key)
    results = {}
    for section in SECTIONS:
        results[section["key"]] = research_section(client, section)

    print(f"\n[2/3] Building card...")
    card = build_card(results, date_str, edition)

    if dry_run:
        print("\n── DRY RUN ──")
        for section in SECTIONS:
            items = results[section["key"]].get("items", [])
            print(f"\n{section['emoji']} {section['label']} ({len(items)} items)")
            for item in items:
                print(f"  • {item.get('headline', '')}")
                print(f"    {item.get('url', '')}")
        print()
    else:
        print(f"\n[3/3] Posting to Teams...")
        post_to_teams(webhook_url, card)
        print(f"\n✓ Done — {edition}\n")


if __name__ == "__main__":
    main()
