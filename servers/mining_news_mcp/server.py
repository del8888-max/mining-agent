"""
Mining News MCP Server — 矿业新闻聚合
Tools: search(query, days), fetch_article(url)
"""

import json
import hashlib
import datetime
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Mock news database ─────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

MOCK_NEWS = [
    {
        "id": "n001",
        "title": "Pilbara Minerals ramps up Pilgangoora expansion to 1Mtpa spodumene concentrate",
        "source": "Mining.com",
        "url": "https://www.mining.com/pilbara-minerals-ramps-up-pilgangoora-expansion",
        "date": "2026-05-25",
        "tags": ["lithium", "Pilbara", "Australia", "spodumene", "production"],
        "summary": "Pilbara Minerals announced the completion of its Pilgangoora expansion project, reaching 1Mtpa spodumene concentrate capacity. The A$560M expansion includes a new processing plant and increased mining fleet.",
        "body": (
            "Pilbara Minerals (ASX: PLS) has successfully commissioned the Pilgangoora expansion, "
            "doubling its spodumene concentrate production capacity to 1 million tonnes per annum. "
            "The expansion, completed on budget at A$560 million, positions PLS as one of the largest "
            "lithium hard-rock producers globally. CEO Dale Henderson stated: 'This milestone reflects "
            "the strong demand outlook for lithium raw materials driven by the energy transition.' "
            "First concentrate from the new train is expected in June 2026, with full ramp-up by Q3 2026."
        )
    },
    {
        "id": "n002",
        "title": "Australia tightens critical minerals foreign investment rules amid lithium supply chain concerns",
        "source": "Australian DISR",
        "url": "https://www.industry.gov.au/news/critical-minerals-foreign-investment-update-2026",
        "date": "2026-05-24",
        "tags": ["policy", "Australia", "critical minerals", "foreign investment", "lithium"],
        "summary": "The Australian government updated foreign investment guidelines for critical minerals, requiring FIRB approval for any acquisition above 10% in lithium and rare earth projects.",
        "body": (
            "The Department of Industry, Science and Resources (DISR) has released updated foreign "
            "investment guidelines that lower the threshold for FIRB review of critical minerals "
            "investments. Any foreign acquisition exceeding 10% equity in an Australian lithium, "
            "rare earth, or cobalt project now requires mandatory review. Treasurer Jim Chalmers "
            "cited 'the strategic importance of maintaining sovereign capability in critical minerals "
            "processing and supply chains.' The rules take effect July 1, 2026."
        )
    },
    {
        "id": "n003",
        "title": "Lithium carbonate prices stabilize after 18-month decline as EV demand rebounds",
        "source": "S&P Global Mining",
        "url": "https://www.spglobal.com/marketintelligence/lithium-prices-stabilize-2026",
        "date": "2026-05-23",
        "tags": ["lithium", "price", "EV", "market"],
        "summary": "Lithium carbonate prices in China stabilized at CNY 85,000/t in May 2026, after falling from CNY 600,000/t in late 2024. EV sales in China surged 35% YoY, supporting demand recovery.",
        "body": (
            "After an 18-month bear market, lithium carbonate spot prices in China appear to have "
            "found a floor at approximately CNY 85,000 per tonne. The stabilization coincides with "
            "a 35% year-over-year surge in Chinese EV sales for April 2026. Market analysts at S&P "
            "Global note that 'inventory destocking across the battery supply chain is largely complete, "
            "and cathode manufacturers are returning to the spot market.' However, significant latent "
            "capacity in lepidolite mines in Jiangxi could cap price recovery in the near term."
        )
    },
    {
        "id": "n004",
        "title": "Ganfeng Lithium secures offtake agreement with Pilbara Minerals for 150kt spodumene",
        "source": "Mining.com",
        "url": "https://www.mining.com/ganfeng-pilbara-offtake-agreement-2026",
        "date": "2026-05-22",
        "tags": ["lithium", "Pilbara", "Ganfeng", "offtake", "China-Australia"],
        "summary": "China's Ganfeng Lithium signed a 5-year offtake agreement with Pilbara Minerals for 150,000 tonnes per year of spodumene concentrate, strengthening China-Australia lithium trade ties.",
        "body": (
            "Ganfeng Lithium, China's largest lithium compound producer, has signed a binding offtake "
            "agreement with Pilbara Minerals for the supply of 150,000 dry metric tonnes of spodumene "
            "concentrate annually over five years starting 2027. The agreement, priced on a formula "
            "linked to Fastmarkets' spodumene index, represents approximately 15% of Pilgangoora's "
            "expanded production capacity. The deal signals continued Chinese appetite for Australian "
            "hard-rock lithium despite ongoing efforts to diversify supply chains."
        )
    },
    {
        "id": "n005",
        "title": "Chile's SQM reports 28% production increase at Atacama lithium brine operations",
        "source": "S&P Global Mining",
        "url": "https://www.spglobal.com/sqm-atacama-production-increase-2026",
        "date": "2026-05-21",
        "tags": ["lithium", "Chile", "SQM", "brine", "production"],
        "summary": "SQM increased lithium carbonate production by 28% YoY to 210,000 tonnes in its Atacama operations, leveraging improved evaporation rates and expanded pond capacity.",
        "body": (
            "Sociedad Química y Minera de Chile (SQM) reported a 28% year-over-year increase in "
            "lithium carbonate production at its Atacama Salar operations, reaching 210,000 tonnes "
            "in Q1 2026. The company attributed the increase to favorable evaporation conditions and "
            "recently commissioned expansion ponds. SQM maintains its full-year guidance of "
            "240,000-250,000 tonnes lithium carbonate equivalent."
        )
    },
    {
        "id": "n006",
        "title": "Rio Tinto's Jadar lithium project faces renewed environmental protests in Serbia",
        "source": "Mining.com",
        "url": "https://www.mining.com/rio-tinto-jadar-protests-2026",
        "date": "2026-05-20",
        "tags": ["lithium", "Rio Tinto", "Serbia", "ESG", "Jadar"],
        "summary": "Environmental groups in Serbia have staged new protests against Rio Tinto's Jadar lithium project, citing water contamination risks. The project remains in permitting limbo.",
        "body": (
            "Thousands of protesters gathered in Belgrade and Loznica over the weekend to oppose "
            "Rio Tinto's proposed Jadar lithium-borate project. Environmental groups presented new "
            "hydrological studies suggesting potential contamination of the Jadar River aquifer. "
            "Rio Tinto responded that its updated Environmental Impact Assessment addresses all "
            "water management concerns. The Serbian government has postponed its final permitting "
            "decision to Q4 2026, creating continued uncertainty for European lithium supply."
        )
    },
    {
        "id": "n007",
        "title": "Copper price hits $10,200/t on LME amid supply deficit fears from Panama mine closure",
        "source": "S&P Global Mining",
        "url": "https://www.spglobal.com/copper-prices-lme-panama-2026",
        "date": "2026-05-25",
        "tags": ["copper", "LME", "Panama", "supply", "price"],
        "summary": "LME copper prices reached $10,200/t, the highest since March 2025, driven by persistent supply concerns after the Cobre Panama mine closure and strong Chinese demand.",
        "body": (
            "Copper prices on the London Metal Exchange breached $10,200 per tonne on Wednesday, "
            "reaching levels not seen since early 2025. The rally was fueled by ongoing supply tightness "
            "following the permanent closure of First Quantum's Cobre Panama mine, which previously "
            "supplied 1.5% of global copper output. Combined with stronger-than-expected Chinese "
            "manufacturing PMI data and green energy demand, analysts forecast a 400,000-tonne "
            "deficit for 2026."
        )
    },
    {
        "id": "n008",
        "title": "China tightens rare earth export controls, impacting global magnet supply chain",
        "source": "Mining.com",
        "url": "https://www.mining.com/china-rare-earth-export-controls-2026",
        "date": "2026-05-19",
        "tags": ["rare earth", "China", "export", "policy", "supply chain"],
        "summary": "China's Ministry of Commerce announced stricter export licensing for rare earth elements, including neodymium and praseodymium, effective June 2026.",
        "body": (
            "China's Ministry of Commerce has announced new export control measures covering rare "
            "earth elements critical for permanent magnet production, including neodymium, praseodymium, "
            "dysprosium, and terbium. Exporters will be required to obtain licenses specifying end-use "
            "and end-user information. The measures, effective June 15, 2026, are widely seen as a "
            "response to US and EU tariffs on Chinese EVs and represent a significant escalation in "
            "critical minerals trade tensions."
        )
    },
    {
        "id": "n009",
        "title": "Liontown Resources commences lithium production at Kathleen Valley with first shipment to LGES",
        "source": "Mining.com",
        "url": "https://www.mining.com/liontown-kathleen-valley-first-shipment-2026",
        "date": "2026-05-18",
        "tags": ["lithium", "Liontown", "Australia", "production", "LG Energy"],
        "summary": "Liontown Resources shipped its first 20,000t spodumene cargo from Kathleen Valley to LG Energy Solution, marking a new Australian lithium producer entering the market.",
        "body": (
            "Liontown Resources (ASX: LTR) has achieved first production and shipment from its "
            "Kathleen Valley lithium project in Western Australia. The maiden 20,000-tonne spodumene "
            "concentrate shipment is destined for LG Energy Solution under a 5-year offtake agreement. "
            "Kathleen Valley is targeting 3Mtpa of ore processing, producing approximately 500,000tpa "
            "of spodumene concentrate at steady state by 2027."
        )
    },
    {
        "id": "n010",
        "title": "Iron ore prices under pressure as Chinese steel output cuts loom for Q3 2026",
        "source": "S&P Global Mining",
        "url": "https://www.spglobal.com/iron-ore-china-steel-cuts-2026",
        "date": "2026-05-17",
        "tags": ["iron ore", "China", "steel", "price", "production"],
        "summary": "Iron ore futures fell to $95/t on the Dalian exchange amid expectations that China will mandate steel production cuts of 15-20Mt in H2 2026 to meet carbon targets.",
        "body": (
            "Iron ore prices are facing renewed downward pressure as the Chinese government signals "
            "steel production cuts of 15-20 million tonnes for the second half of 2026. The mandated "
            "reductions are part of China's carbon peaking action plan for the steel sector. "
            "Dalian iron ore futures fell to $95/t, down from $115/t in April. Australian producers "
            "BHP, Rio Tinto, and Fortescue are closely monitoring the policy development, which could "
            "reduce seaborne iron ore demand by 30-40Mt on an annualized basis."
        )
    },
]

# Index news by id for fast lookup
NEWS_BY_ID = {n["id"]: n for n in MOCK_NEWS}


def _generate_id(title: str) -> str:
    return "n" + hashlib.md5(title.encode()).hexdigest()[:6]


# ── MCP Server ─────────────────────────────────────────────────────
app = Server("mining-news-mcp")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="search",
            description=(
                "搜索矿业新闻。按关键词和天数搜索新闻数据库，返回匹配的新闻列表。"
                "Search mining news by keyword and recency in days."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词, e.g. 'lithium Pilbara', 'copper price', 'rare earth policy'"
                    },
                    "days": {
                        "type": "integer",
                        "description": "搜索最近多少天的新闻, default 30",
                        "default": 30
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="fetch_article",
            description=(
                "获取单篇新闻的完整内容。根据URL或文章ID返回新闻全文。"
                "Fetch full article content by URL or article ID."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "新闻URL或文章ID (e.g. 'n001')"
                    }
                },
                "required": ["url"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search":
        return await _search(arguments)
    elif name == "fetch_article":
        return await _fetch_article(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _search(args: dict) -> list[TextContent]:
    query = args["query"].lower()
    days = args.get("days", 30)

    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    results = []
    query_terms = query.split()
    for news in MOCK_NEWS:
        if news["date"] < cutoff:
            continue
        haystack = f"{news['title']} {news['summary']} {' '.join(news['tags'])}".lower()
        if all(term in haystack for term in query_terms):
            results.append({
                "id": news["id"],
                "title": news["title"],
                "source": news["source"],
                "url": news["url"],
                "date": news["date"],
                "tags": news["tags"],
                "summary": news["summary"],
            })

    return [TextContent(
        type="text",
        text=json.dumps({
            "query": args["query"],
            "days": days,
            "count": len(results),
            "results": results
        }, ensure_ascii=False, indent=2)
    )]


async def _fetch_article(args: dict) -> list[TextContent]:
    url = args["url"]

    # Try to find by ID first, then by URL
    article = NEWS_BY_ID.get(url)
    if not article:
        for n in MOCK_NEWS:
            if n["url"] == url:
                article = n
                break

    if not article:
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Article not found: {url}"}, ensure_ascii=False)
        )]

    return [TextContent(
        type="text",
        text=json.dumps({
            "id": article["id"],
            "title": article["title"],
            "source": article["source"],
            "url": article["url"],
            "date": article["date"],
            "tags": article["tags"],
            "summary": article["summary"],
            "full_text": article["body"]
        }, ensure_ascii=False, indent=2)
    )]


async def main():
    async with stdio_server() as (reader, writer):
        await app.run(reader, writer, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
