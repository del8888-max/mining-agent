"""
Mining Daily Agent Orchestrator — 矿权日报编排引擎

ReAct-style agent that orchestrates 3 MCP servers:
  1. mining-news-mcp  — news search & fetch
  2. mineral-pdf-mcp  — NI 43-101 resource extraction
  3. lme-price-mcp    — commodity price data

Input:  natural language (e.g. "给我生成一份关于 Pilbara 锂矿的今日简报")
Output: Markdown briefing with news summary + reserves + prices + risks + sources
"""

import os
import json
import asyncio
import sys
import datetime
from pathlib import Path
from typing import Any

# ── MCP client imports ─────────────────────────────────────────────
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVERS_DIR = Path(__file__).resolve().parent.parent / "servers"

SERVER_CONFIGS = {
    "mining-news": {
        "command": sys.executable,
        "args": [str(SERVERS_DIR / "mining_news_mcp" / "server.py")],
    },
    "mineral-pdf": {
        "command": sys.executable,
        "args": [str(SERVERS_DIR / "mineral_pdf_mcp" / "server.py")],
    },
    "lme-price": {
        "command": sys.executable,
        "args": [str(SERVERS_DIR / "lme_price_mcp" / "server.py")],
    },
}

# ── System prompt for the ReAct agent ──────────────────────────────
SYSTEM_PROMPT = """You are a mining industry analyst agent. Your job is to generate a comprehensive daily briefing about mineral rights, mining projects, and commodity markets.

You have access to 3 MCP tools across 3 servers:

**mining-news-mcp:**
- search(query, days) — search mining news by keyword
- fetch_article(url) — get full article content by URL or ID

**mineral-pdf-mcp:**
- extract_resources(pdf_url) — extract NI 43-101 mineral reserves & resources from PDF
- list_available_reports() — list all available technical reports

**lme-price-mcp:**
- get_price(commodity, date) — get commodity price for a date
- get_trend(commodity, days) — get price trend for N days
- list_commodities() — list all supported commodities

When the user asks for a briefing on a topic (e.g. "Pilbara lithium"), you MUST:

1. Search for recent news about the topic: call mining-news.search(query, days=7)
2. Get price trends for relevant commodities: call lme-price.get_trend(commodity, days=30)
3. Extract resource data from relevant NI 43-101 reports: call mineral-pdf.extract_resources(pdf_url)
4. If needed, fetch full article text for important news

After gathering data, generate a Markdown briefing with:
- **今日新闻摘要** (Today's News Summary)
- **储量与资源数据** (Reserves & Resources from NI 43-101)
- **价格走势** (Price Trends)
- **风险提示** (Risk Warnings)
- **信息来源** (Source Links)

Run all independent tool calls in parallel when possible. Write in Chinese (Simplified).
"""

TOOL_DEFINITIONS = [
    {
        "name": "mining-news.search",
        "description": "搜索矿业新闻。Search mining news by keyword and days. Input: query (string), days (int, default 7).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词, e.g. 'Pilbara lithium', 'copper price'"},
                "days": {"type": "integer", "description": "搜索最近多少天, default 7"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "mining-news.fetch_article",
        "description": "获取单篇新闻全文。Fetch full article by URL or ID. Input: url (string).",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "文章URL或ID, e.g. 'n001'"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "mineral-pdf.extract_resources",
        "description": "从NI 43-101 PDF提取储量和资源数据。Extract mineral reserves/resources from PDF. Input: pdf_url (string).",
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_url": {"type": "string", "description": "NI 43-101 PDF URL"}
            },
            "required": ["pdf_url"]
        }
    },
    {
        "name": "mineral-pdf.list_available_reports",
        "description": "列出所有可用的NI 43-101报告。List all available technical reports.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "lme-price.get_price",
        "description": "获取商品价格。Get commodity price for a date. Input: commodity (string), date (string YYYY-MM-DD).",
        "input_schema": {
            "type": "object",
            "properties": {
                "commodity": {"type": "string", "description": "商品名称, 中文或英文, e.g. '锂', 'copper', '铁矿石'"},
                "date": {"type": "string", "description": "日期 YYYY-MM-DD"}
            },
            "required": ["commodity"]
        }
    },
    {
        "name": "lme-price.get_trend",
        "description": "获取商品价格走势。Get price trend for last N days. Input: commodity (string), days (int, default 30).",
        "input_schema": {
            "type": "object",
            "properties": {
                "commodity": {"type": "string", "description": "商品名称"},
                "days": {"type": "integer", "description": "查询最近多少天, default 30"}
            },
            "required": ["commodity"]
        }
    },
    {
        "name": "lme-price.list_commodities",
        "description": "列出所有支持的商品及当前价格。",
        "input_schema": {"type": "object", "properties": {}}
    },
]


class MCPClientPool:
    """Manages connections to multiple MCP servers."""

    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self._contexts: dict[str, Any] = {}

    async def connect(self, name: str) -> ClientSession:
        if name in self.sessions:
            return self.sessions[name]

        config = SERVER_CONFIGS[name]
        params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
        )
        # stdio_client returns (read, write)
        ctx = stdio_client(params)
        read, write = await ctx.__aenter__()

        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        self._contexts[name] = (ctx, read, write)
        self.sessions[name] = session
        return session

    async def close(self):
        for session in self.sessions.values():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass
        for (ctx, read, write) in self._contexts.values():
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                pass

    async def call_tool(self, server: str, tool_name: str, arguments: dict) -> str:
        session = await self.connect(server)
        result = await session.call_tool(tool_name, arguments)
        # Extract text from result content
        texts = []
        for item in result.content:
            if hasattr(item, "text"):
                texts.append(item.text)
        return "\n".join(texts)


async def run_demo_mode(query: str) -> str:
    """
    Demo mode: keyword-based dispatch without LLM.
    Extracts topic keywords from query and directly calls relevant MCP tools.
    """
    pool = MCPClientPool()
    try:
        # ── Parse query for key signals ─────────────────────────
        query_lower = query.lower()
        has_lithium = any(w in query_lower for w in ["锂", "lithium", "li "])
        has_copper = any(w in query_lower for w in ["铜", "copper", "cu "])
        has_gold = any(w in query_lower for w in ["金", "gold", "au "])
        has_iron = any(w in query_lower for w in ["铁", "iron", "fe "])
        has_pilbara = any(w in query_lower for w in ["pilbara", "pilgangoora", "皮尔巴拉"])
        has_rare_earth = any(w in query_lower for w in ["稀土", "rare earth", "ndpr", "钕"])

        # Determine topic keywords
        if has_pilbara or has_lithium:
            topic = "Pilbara lithium"
            news_query = "Pilbara lithium"
            commodities = ["锂辉石", "碳酸锂"]
            pdf_url = "https://www.pilbaraminerals.com.au/investors/pilgangoora-resource-update-2026.pdf"
        elif has_copper:
            topic = "copper"
            news_query = "copper price supply"
            commodities = ["铜"]
            pdf_url = "https://www.newmont.com/investors/43-101-boddington-2025.pdf"
        elif has_gold:
            topic = "gold"
            news_query = "gold mining"
            commodities = ["黄金"]
            pdf_url = "https://www.barrick.com/investors/43-101-carlin-2025.pdf"
        elif has_iron:
            topic = "iron ore"
            news_query = "iron ore steel"
            commodities = ["铁矿石"]
            pdf_url = "https://www.newmont.com/investors/43-101-boddington-2025.pdf"
        elif has_rare_earth:
            topic = "rare earth"
            news_query = "rare earth policy"
            commodities = ["稀土"]
            pdf_url = "https://www.pilbaraminerals.com.au/investors/pilgangoora-resource-update-2026.pdf"
        else:
            topic = "mining"
            news_query = "mining critical minerals"
            commodities = ["铜", "碳酸锂", "铁矿石"]
            pdf_url = "https://www.pilbaraminerals.com.au/investors/pilgangoora-resource-update-2026.pdf"

        print(f"[Agent] Topic detected: {topic}")
        print(f"[Agent] Gathering data from 3 MCP servers...")

        # ── Parallel: search news + list reports + list commodities ──
        news_result, reports_result, commodities_result = await asyncio.gather(
            pool.call_tool("mining-news", "search", {"query": news_query, "days": 7}),
            pool.call_tool("mineral-pdf", "list_available_reports", {}),
            pool.call_tool("lme-price", "list_commodities", {}),
        )

        # ── Parallel: price trends + PDF extraction ──
        price_tasks = [
            pool.call_tool("lme-price", "get_trend", {"commodity": c, "days": 30})
            for c in commodities
        ]
        pdf_task = pool.call_tool("mineral-pdf", "extract_resources", {"pdf_url": pdf_url})

        all_results = await asyncio.gather(pdf_task, *price_tasks)
        pdf_result = all_results[0]
        price_results = list(all_results[1:])

        # ── Build Markdown briefing ─────────────────────────────
        return _build_briefing(
            topic=topic,
            news_json=news_result,
            pdf_json=pdf_result,
            price_jsons=price_results,
            commodity_names=commodities,
        )

    finally:
        await pool.close()


def _build_briefing(
    topic: str,
    news_json: str,
    pdf_json: str,
    price_jsons: list[str],
    commodity_names: list[str],
) -> str:
    """Build a Markdown briefing from tool results."""
    news_data = json.loads(news_json)
    pdf_data = json.loads(pdf_json)
    price_data = [json.loads(p) for p in price_jsons]
    today = datetime.date.today().isoformat()

    lines = []
    lines.append(f"# 矿权日报 — {topic.upper()} 简报")
    lines.append(f"**生成日期**: {today}")
    lines.append(f"**数据来源**: Mining.com, S&P Global Mining, LME, NI 43-101 技术报告")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Section 1: News Summary ──────────────────────────────────
    lines.append("## 今日新闻摘要")
    lines.append("")
    articles = news_data.get("results", [])[:5]
    if not articles:
        lines.append("> *近7天无相关新闻。*")
    else:
        for i, a in enumerate(articles, 1):
            lines.append(f"### {i}. {a['title']}")
            lines.append(f"- **来源**: {a['source']} | **日期**: {a['date']}")
            lines.append(f"- **链接**: {a['url']}")
            lines.append(f"- {a['summary']}")
            lines.append("")
            # Add tags
            tags_str = ", ".join(f"`{t}`" for t in a.get("tags", []))
            lines.append(f"  标签: {tags_str}")
            lines.append("")

    # ── Section 2: Reserves & Resources ──────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 储量与资源数据 (NI 43-101)")
    lines.append("")

    if "error" in pdf_data:
        lines.append(f"> *无法提取储量数据: {pdf_data['error']}*")
    else:
        lines.append(f"**报告**: {pdf_data['report_name']}")
        lines.append(f"**公司**: {pdf_data['company']}")
        lines.append(f"**生效日期**: {pdf_data['effective_date']}")
        lines.append(f"**合资格人士**: {pdf_data['qualified_person']}")
        lines.append("")

        # Mineral Reserves table
        reserves = pdf_data.get("mineral_reserves", {})
        if reserves:
            lines.append("### 矿产储量 (Mineral Reserves)")
            lines.append("")
            lines.append("| 类别 | 矿石量 (Mt) | 品位 | 金属量 |")
            lines.append("|------|-----------|------|--------|")
            for cat, data in reserves.items():
                ore = data.get("ore_tonnes_mt", "—")
                # Determine grade field
                grade = "—"
                if "gold_grade_gpt" in data:
                    grade = f"{data['gold_grade_gpt']} g/t Au"
                elif "li2o_grade_pct" in data:
                    grade = f"{data['li2o_grade_pct']}% Li2O"
                if "copper_grade_pct" in data and data.get("copper_grade_pct", 0) > 0:
                    grade += f" + {data['copper_grade_pct']}% Cu"
                # Metal content
                metal = "—"
                if "contained_gold_moz" in data:
                    metal = f"{data['contained_gold_moz']} Moz Au"
                elif "contained_lio2_kt" in data:
                    metal = f"{data['contained_lio2_kt']} kt Li2O"
                lines.append(f"| {cat} | {ore} | {grade} | {metal} |")
            lines.append("")

        # Mineral Resources table
        resources = pdf_data.get("mineral_resources", {})
        if resources:
            lines.append("### 矿产资源 (Mineral Resources)")
            lines.append("")
            lines.append("| 类别 | 矿石量 (Mt) | 品位 |")
            lines.append("|------|-----------|------|")
            for cat, data in resources.items():
                ore = data.get("ore_tonnes_mt", "—")
                grade = "—"
                if "gold_grade_gpt" in data:
                    grade = f"{data['gold_grade_gpt']} g/t Au"
                elif "li2o_grade_pct" in data:
                    grade = f"{data['li2o_grade_pct']}% Li2O"
                lines.append(f"| {cat} | {ore} | {grade} |")
            lines.append("")

    # ── Section 3: Price Trends ──────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 价格走势")
    lines.append("")

    for i, (pdata, cname) in enumerate(zip(price_data, commodity_names)):
        if "error" in pdata:
            lines.append(f"### {cname}: 数据不可用")
            continue
        summary = pdata.get("summary", {})
        lines.append(f"### {cname} ({summary.get('unit', '—')})")
        lines.append("")
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 周期 | {summary.get('days', '—')} 天 |")
        lines.append(f"| 起始 ({summary.get('start_date', '—')}) | {summary.get('start_price', '—')} |")
        lines.append(f"| 当前 ({summary.get('end_date', '—')}) | {summary.get('end_price', '—')} |")
        lines.append(f"| 变动 | {summary.get('change_pct', '—')}% |")
        lines.append(f"| 最高 | {summary.get('high', '—')} |")
        lines.append(f"| 最低 | {summary.get('low', '—')} |")
        lines.append(f"| 均价 | {summary.get('avg', '—')} |")
        lines.append("")

        # Mini trend chart (ASCII)
        daily = pdata.get("daily_prices", [])
        if len(daily) > 5:
            prices = [d["price"] for d in daily]
            pmin, pmax = min(prices), max(prices)
            prange = pmax - pmin or 1
            chart = ""
            for j, d in enumerate(daily):
                if j % max(1, len(daily) // 20) == 0:
                    bar_len = int((d["price"] - pmin) / prange * 10)
                    chart += f"  {d['date']} {'█' * bar_len} {d['price']}\n"
            lines.append("```")
            lines.append(chart.rstrip())
            lines.append("```")
            lines.append("")

    # ── Section 4: Risk Warnings ─────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 风险提示")
    lines.append("")

    risks_noted = pdf_data.get("risks_noted", [])
    if not isinstance(risks_noted, list):
        risks_noted = []

    # General risk assessment based on data
    all_risks = list(risks_noted)

    # Price risk
    for pdata, cname in zip(price_data, commodity_names):
        summary = pdata.get("summary", {})
        change = summary.get("change_pct", 0)
        if abs(change) > 5:
            direction = "上涨" if change > 0 else "下跌"
            all_risks.append(f"⚠️ **{cname}价格波动风险**: 近30天变动 {change}%, 持续{direction}趋势")

    # News risk signals
    for article in articles:
        title_lower = article.get("title", "").lower()
        if any(w in title_lower for w in ["risk", "环境", "protest", "抗议", "regulation", "监管", "export control", "关税"]):
            all_risks.append(f"🔶 **政策/ESG风险**: {article['title']}")

    if not all_risks:
        all_risks.append("> 当前未检测到显著风险信号。建议关注全球宏观经济和贸易政策变动。")

    for risk in all_risks:
        lines.append(f"- {risk}")
    lines.append("")

    # ── Section 5: Sources ────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 信息来源")
    lines.append("")
    for a in articles:
        lines.append(f"- [{a['title']}]({a['url']}) — {a['source']} ({a['date']})")
    lines.append(f"- [{pdf_data.get('report_name', 'NI 43-101 Report')}]({pdf_data.get('report_name', '')}) — {pdf_data.get('company', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*免责声明: 本报告由 AI Agent 自动生成, 数据仅供参考, 不构成投资建议。*")
    lines.append(f"*生成时间: {today} | Agent: Mining Daily MCP Agent v1.0*")

    return "\n".join(lines)


# ── LLM-powered ReAct mode (requires ANTHROPIC_API_KEY) ────────────
async def run_react_mode(query: str) -> str:
    """ReAct agent using Anthropic Claude to orchestrate tool calls."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return await run_demo_mode(query)

    client = anthropic.AsyncAnthropic(api_key=api_key)
    pool = MCPClientPool()

    messages = [{"role": "user", "content": query}]
    tool_calls_log = []

    try:
        for _ in range(8):  # max 8 ReAct steps
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            # Check for tool calls
            tool_use_blocks = [
                b for b in response.content if b.type == "tool_use"
            ]

            if not tool_use_blocks:
                # Final answer — no more tools needed
                return _extract_text(response.content)

            # Execute all tool calls in parallel
            messages.append({
                "role": "assistant",
                "content": response.content,
            })

            tool_results = []
            tasks = []
            for block in tool_use_blocks:
                server, tool_name = block.name.split(".", 1)
                print(f"[ReAct] Calling {block.name}({json.dumps(block.input, ensure_ascii=False)})")
                tasks.append((block, pool.call_tool(server, tool_name, block.input)))

            # Execute in parallel
            results = await asyncio.gather(*[t[1] for t in tasks])

            tool_result_content = []
            for (block, _), result_text in zip(tasks, results):
                tool_calls_log.append({
                    "tool": block.name,
                    "input": block.input,
                    "output": result_text[:500] + ("..." if len(result_text) > 500 else ""),
                })
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

            messages.append({
                "role": "user",
                "content": tool_result_content,
            })

        # Fallback: if we hit the loop limit, return what we have
        return _build_fallback_briefing(tool_calls_log)

    finally:
        await pool.close()


def _extract_text(content) -> str:
    for block in content:
        if block.type == "text":
            return block.text
    return str(content)


def _build_fallback_briefing(tool_calls_log: list) -> str:
    """Build a basic briefing from logged tool calls if LLM didn't finish."""
    lines = ["# 矿权日报 — 自动生成简报", ""]
    lines.append("> ⚠️ Agent 达到最大推理步数, 以下是已收集数据的摘要。")
    lines.append("")
    for call in tool_calls_log:
        lines.append(f"## {call['tool']}")
        lines.append(f"输入: `{json.dumps(call['input'], ensure_ascii=False)}`")
        lines.append("")
        lines.append("```json")
        lines.append(call['output'][:1000])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


# ── Main entry ─────────────────────────────────────────────────────
async def main():
    # Ensure console output works on Windows GBK terminals
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  矿权日报 Agent — Mining Daily MCP Agent")
    print("=" * 60)
    print()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "给我生成一份关于 Pilbara 锂矿的今日简报"
        print(f"默认查询: {query}")
        print()

    # Try ReAct mode first, fall back to demo mode
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("[Agent] 使用 LLM ReAct 模式 (Claude)...")
        report = await run_react_mode(query)
    else:
        print("[Agent] 使用 Demo 模式 (无 ANTHROPIC_API_KEY)...")
        print("[Agent] 设置 ANTHROPIC_API_KEY 环境变量可启用 LLM ReAct 模式。")
        print()
        report = await run_demo_mode(query)

    print()
    print(report)

    # Save report
    output_path = Path(__file__).resolve().parent.parent / "briefing_output.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"\n[Agent] 简报已保存至: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
