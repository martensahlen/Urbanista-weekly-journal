"""
Urbanista Monday Brief — Agent
Forces current week news with date-aware prompts.
"""

import os, sys, json, datetime, re, requests, anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL = "claude-sonnet-4-6"

def get_date_context():
    now = datetime.datetime.now()
    week_start = now - datetime.timedelta(days=now.weekday())
    return {
        "today": now.strftime("%B %d, %Y"),
        "week_start": week_start.strftime("%B %d, %Y"),
        "month": now.strftime("%B %Y"),
        "year": str(now.year)
    }

def make_sections(d):
    return [
        {
            "key": "market",
            "label": "Market Update",
            "emoji": "🌍",
            "prompt": f'Today is {d["today"]}. Search for NEWS published this week (after {d["week_start"]}) about the consumer audio market — headphones, earphones, Bluetooth speakers — in North America, Europe, UK, Australia and New Zealand. Search specifically for: "headphone market {d["month"]}", "audio sales {d["year"]}", "consumer electronics news {d["today"]}". Find 5 actual news stories published recently. For each use the real URL of the article. Return ONLY this JSON with no other text:\n{{"items":[{{"tag":"region","headline":"actual news headline from this week","body":"What happened and why it matters. 2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"region","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"region","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"region","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"region","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}}]}}'
        },
        {
            "key": "product",
            "label": "Product News",
            "emoji": "🎯",
            "prompt": f'Today is {d["today"]}. Search for NEWS published this week (after {d["week_start"]}) about these audio brands: Nothing, JLab, JBL, Soundcore, Marshall, Sudio. Search for: "Nothing audio {d["month"]}", "JBL new {d["month"]}", "Soundcore {d["month"]}", "Marshall headphones news {d["year"]}", "Sudio {d["year"]}". Find 5 actual recent news stories — product launches, campaigns, pricing, retail moves. Use real article URLs. Return ONLY this JSON:\n{{"items":[{{"tag":"Brand","headline":"actual news headline","body":"What happened. 2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Brand","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Brand","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Brand","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Brand","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}}]}}'
        },
        {
            "key": "retail",
            "label": "Retail",
            "emoji": "🏪",
            "prompt": f'Today is {d["today"]}. Search for NEWS published this week (after {d["week_start"]}) about consumer electronics retail. Search for: "Best Buy {d["month"]}", "MediaMarkt {d["month"]}", "Amazon electronics {d["month"]}", "airport retail {d["year"]}", "DTC ecommerce {d["month"]}". Find 5 actual recent news stories about retail changes, shelf resets, sales data, DTC trends, or travel retail. Use real article URLs. Return ONLY this JSON:\n{{"items":[{{"tag":"Retailer","headline":"actual news headline","body":"What happened. 2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Retailer","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Retailer","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Retailer","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Retailer","headline":"actual news headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}}]}}'
        },
        {
            "key": "compliance",
            "label": "Compliance",
            "emoji": "⚖️",
            "prompt": f'Today is {d["today"]}. Search for regulatory and compliance NEWS published recently (after {d["week_start"]}) affecting consumer electronics in EU, US, UK, Canada, Australia. Search for: "FCC ruling {d["month"]}", "EU electronics regulation {d["month"]}", "UKCA compliance {d["year"]}", "battery regulation {d["month"]}", "consumer electronics compliance {d["month"]}". Find 5 actual recent regulatory updates, notices, or enforcement actions. Use real URLs to official sources or news articles. Return ONLY this JSON:\n{{"items":[{{"tag":"Market","headline":"actual regulatory headline","body":"What changed and the implication. 2 sentences.","url":"https://actual-source-url.com","source":"Source Name"}},{{"tag":"Market","headline":"actual headline","body":"2 sentences.","url":"https://actual-source-url.com","source":"Source Name"}},{{"tag":"Market","headline":"actual headline","body":"2 sentences.","url":"https://actual-source-url.com","source":"Source Name"}},{{"tag":"Market","headline":"actual headline","body":"2 sentences.","url":"https://actual-source-url.com","source":"Source Name"}},{{"tag":"Market","headline":"actual headline","body":"2 sentences.","url":"https://actual-source-url.com","source":"Source Name"}}]}}'
        },
        {
            "key": "ai",
            "label": "AI Tips & Tricks",
            "emoji": "✦",
            "prompt": f'Today is {d["today"]}. Search for practical AI news and tips published recently (after {d["week_start"]}) for small businesses and product companies (10-20 people). Search for: "AI for small business {d["month"]}", "Claude tips {d["month"]}", "ChatGPT workflow {d["month"]}", "AI productivity {d["month"]}", "AI tools {d["month"]}". Find 5 actionable and current AI use cases or tool updates relevant to Finance, Operations, Logistics, Sales, or Product. Use real article URLs. Return ONLY this JSON:\n{{"items":[{{"tag":"Function","headline":"actual tip or news headline","body":"What it is and how to use it. 2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Function","headline":"actual headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Function","headline":"actual headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Function","headline":"actual headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}},{{"tag":"Function","headline":"actual headline","body":"2 sentences.","url":"https://actual-article-url.com","source":"Publisher Name"}}]}}'
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
        text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text.strip()]
        for text in reversed(text_blocks):
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                try:
                    result = json.loads(text[start:end])
                    if result.get("items"):
                        result["items"] = result["items"][:5]
                        print(f"    ✓ {section['label']}: {len(result['items'])} items")
                        return section["key"], result
                except json.JSONDecodeError:
                    pass
        print(f"    ⚠️  No valid JSON found")
        return section["key"], {"items": []}
    except Exception as e:
        print(f"    ⚠️  Exception: {e}")
        return section["key"], {"items": []}


def generate_intro(client, results):
    print("  → ✍️  Writing intro...")
    headlines = []
    for section in make_sections(get_date_context())[:3]:
        items = results.get(section["key"], {}).get("items", [])
        if items:
            headlines.append(items[0].get("headline", ""))
    prompt = f"Write a 2-sentence editorial intro for Urbanista's Monday Brief — a weekly intelligence report for a premium audio brand. Tone: sharp, informed, like a smart colleague summarising the week. Based on these top stories this week: {' | '.join(headlines)}. Respond with ONLY the 2 sentences, nothing else."
    try:
        response = client.messages.create(
            model=MODEL, max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"    ⚠️  Intro error: {e}")
        return "Another week of signals worth reading. Here's what moved in audio, retail, compliance, and AI."


def build_card(results, intro, date_str, edition, sections):
    body = [
        {"type": "TextBlock", "text": f"URBANISTA MONDAY BRIEF · {edition}",
         "weight": "Bolder", "size": "Medium", "wrap": True},
        {"type": "TextBlock", "text": date_str,
         "isSubtle": True, "size": "Small", "spacing": "None"},
        {"type": "TextBlock", "text": intro,
         "wrap": True, "size": "Medium", "spacing": "Medium", "isSubtle": True}
    ]

    for section in sections:
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
    d = get_date_context()
    sections = make_sections(d)

    print(f"\n📰 Urbanista Monday Brief — {date_str}")
    print(f"   Searching for news from {d['week_start']} onwards")
    print("=" * 52)
    print("\n[1/3] Running all sections in parallel...")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(research_section, s): s for s in sections}
        for future in as_completed(futures):
            key, data = future.result()
            results[key] = data

    print("\n[2/3] Writing intro and building card...")
    intro = generate_intro(client, results)
    card = build_card(results, intro, date_str, edition, sections)

    if dry_run:
        print("\n── DRY RUN ──")
        print(f"\nIntro: {intro}\n")
        for section in sections:
            items = results[section["key"]].get("items", [])
            print(f"{section['emoji']} {section['label']} ({len(items)} items)")
            for item in items:
                print(f"  • {item.get('headline','')}")
                print(f"    {item.get('url','')}")
    else:
        print("\n[3/3] Posting to Teams...")
        r = requests.post(os.environ["TEAMS_WEBHOOK_URL"], json=card,
                          headers={"Content-Type": "application/json"}, timeout=30)
        r.raise_for_status()
        print(f"  ✓ Posted (HTTP {r.status_code})")

    print(f"\n✓ Done — {edition}\n")


if __name__ == "__main__":
    main()
