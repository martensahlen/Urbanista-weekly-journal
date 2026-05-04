"""
Urbanista Monday Brief — Final Agent
Runs all sections in parallel for speed. 3 items per section.

Setup:
  pip install anthropic requests
  export ANTHROPIC_API_KEY=sk-ant-...
  export TEAMS_WEBHOOK_URL=https://prod-xx.logic.azure.com/...
"""

import os, sys, json, datetime, re, requests, anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL = "claude-sonnet-4-6"

SECTIONS = [
    {
        "key": "market",
        "label": "Market Update",
        "emoji": "🌍",
        "prompt": """Search the web for latest news (past 2 weeks) about the consumer audio market — TWS, headphones, speakers — in North America, Europe, UK, Australia, New Zealand. Find 3 findings about trends, pricing, or consumer behaviour.

Respond with ONLY this JSON, no other text:
{"items":[{"tag":"Region","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Region","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Region","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"}]}"""
    },
    {
        "key": "product",
        "label": "Product News",
        "emoji": "🎯",
        "prompt": """Search the web for latest news (past 2 weeks) about these audio brands: Nothing, JLab, JBL, Soundcore, Marshall, Sudio. Find 3 notable updates — new products, pricing, or campaigns.

Respond with ONLY this JSON, no other text:
{"items":[{"tag":"Brand","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Brand","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Brand","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"}]}"""
    },
    {
        "key": "retail",
        "label": "Retail",
        "emoji": "🏪",
        "prompt": """Search the web for latest news (past 2 weeks) about consumer electronics retail — Best Buy, MediaMarkt, Currys, Amazon audio, DTC trends, airport retail. Find 3 relevant updates.

Respond with ONLY this JSON, no other text:
{"items":[{"tag":"Retailer","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Retailer","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Retailer","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"}]}"""
    },
    {
        "key": "compliance",
        "label": "Compliance",
        "emoji": "⚖️",
        "prompt": """Search the web for latest regulatory news (past 4 weeks) for consumer electronics in EU, US, UK, Canada, Australia, New Zealand. Look for FCC notices, battery regulations, CE/UKCA updates, labelling rules. Find 3 updates.

Respond with ONLY this JSON, no other text:
{"items":[{"tag":"Market","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Market","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Market","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"}]}"""
    },
    {
        "key": "ai",
        "label": "AI Tips & Tricks",
        "emoji": "✦",
        "prompt": """Search the web for practical AI tips for small product companies (10-20 people). Find 3 actionable AI use cases for Finance, Operations, Logistics, Sales, or Product teams — using tools like Claude, ChatGPT, Copilot, or Zapier.

Respond with ONLY this JSON, no other text:
{"items":[{"tag":"Function","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Function","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"},{"tag":"Function","headline":"short headline","body":"2 sentences.","url":"https://example.com","source":"Source Name"}]}"""
    }
]


def extract_json(text):
    text = re.sub(r'```json|```', '', text).strip()
    start = text.find('{')
    end = text.rfind('}') + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None


def research_section(section):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    print(f"  → {section['emoji']} {section['label']}...")
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": section["prompt"]}]
            )
            text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text.strip()]
            for text in reversed(text_blocks):
                result = extract_json(text)
                if result and result.get("items"):
                    # Cap at 3 items
                    result["items"] = result["items"][:3]
                    print(f"    ✓ {section['label']}: {len(result['items'])} items")
                    return section["key"], result
            print(f"    ⚠️  {section['label']}: no JSON (attempt {attempt+1})")
        except Exception as e:
            print(f"    ⚠️  {section['label']}: error (attempt {attempt+1}): {e}")
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
