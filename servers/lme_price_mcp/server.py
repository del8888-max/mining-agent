"""
LME Price MCP Server — 矿产价格行情
Tools: get_price(commodity, date), get_trend(commodity, days)
"""

import json
import datetime
import random
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Mock price data ────────────────────────────────────────────────

BASE_PRICES = {
    "lithium_carbonate": {"unit": "CNY/t", "base": 85000, "volatility": 0.03},
    "lithium_hydroxide": {"unit": "CNY/t", "base": 92000, "volatility": 0.03},
    "spodumene_6pct": {"unit": "USD/t FOB Australia", "base": 1100, "volatility": 0.04},
    "copper_lme": {"unit": "USD/t", "base": 10200, "volatility": 0.015},
    "zinc_lme": {"unit": "USD/t", "base": 2850, "volatility": 0.02},
    "nickel_lme": {"unit": "USD/t", "base": 16800, "volatility": 0.025},
    "iron_ore_62pct": {"unit": "USD/dmt CFR China", "base": 95, "volatility": 0.03},
    "gold_lbma": {"unit": "USD/oz", "base": 2450, "volatility": 0.012},
    "silver_lbma": {"unit": "USD/oz", "base": 28.50, "volatility": 0.02},
    "cobalt_sulfate": {"unit": "CNY/t", "base": 42000, "volatility": 0.025},
    "rare_earth_ndpr": {"unit": "CNY/t", "base": 480000, "volatility": 0.03},
}

COMMODITY_ALIASES = {
    "锂": "lithium_carbonate", "lithium": "lithium_carbonate", "li": "lithium_carbonate",
    "碳酸锂": "lithium_carbonate", "氢氧化锂": "lithium_hydroxide",
    "锂辉石": "spodumene_6pct", "spodumene": "spodumene_6pct",
    "铜": "copper_lme", "copper": "copper_lme", "cu": "copper_lme",
    "锌": "zinc_lme", "zinc": "zinc_lme", "zn": "zinc_lme",
    "镍": "nickel_lme", "nickel": "nickel_lme", "ni": "nickel_lme",
    "铁矿石": "iron_ore_62pct", "iron ore": "iron_ore_62pct", "铁": "iron_ore_62pct", "fe": "iron_ore_62pct",
    "黄金": "gold_lbma", "gold": "gold_lbma", "au": "gold_lbma",
    "白银": "silver_lbma", "silver": "silver_lbma", "ag": "silver_lbma",
    "钴": "cobalt_sulfate", "cobalt": "cobalt_sulfate", "co": "cobalt_sulfate",
    "稀土": "rare_earth_ndpr", "rare earth": "rare_earth_ndpr", "钕镨": "rare_earth_ndpr",
}


def _resolve_commodity(name: str) -> str | None:
    name_lower = name.lower().strip()
    if name_lower in BASE_PRICES:
        return name_lower
    return COMMODITY_ALIASES.get(name_lower)


def _generate_price(commodity_key: str, date_str: str) -> dict:
    info = BASE_PRICES[commodity_key]
    base = info["base"]
    vol = info["volatility"]

    seed = hash(f"{commodity_key}:{date_str}") % 10000
    rng = random.Random(seed)

    trend_map = {
        "lithium_carbonate": 0.02, "lithium_hydroxide": 0.02, "spodumene_6pct": 0.02,
        "copper_lme": 0.03, "iron_ore_62pct": -0.04, "gold_lbma": 0.02,
        "rare_earth_ndpr": 0.015,
    }
    trend_factor = trend_map.get(commodity_key, 0.0)

    ref_date = datetime.date(2026, 5, 26)
    try:
        d = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        d = ref_date
    days_offset = (d - ref_date).days

    trend_adjustment = 1.0 + trend_factor * (days_offset / 90)
    noise = rng.gauss(0, vol)
    price = base * trend_adjustment * (1 + noise)

    return {
        "commodity": commodity_key,
        "date": date_str,
        "price": round(price, 2),
        "unit": info["unit"],
        "change_pct": round(noise * 100, 2),
        "trend": "up" if noise > 0 else "down"
    }


def _generate_trend(commodity_key: str, days: int) -> list[dict]:
    end_date = datetime.date(2026, 5, 26)
    result = []
    for i in range(days - 1, -1, -1):
        d = end_date - datetime.timedelta(days=i)
        result.append(_generate_price(commodity_key, d.isoformat()))
    return result


# ── MCP Server ─────────────────────────────────────────────────────
app = Server("lme-price-mcp")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_price",
            description=(
                "获取指定商品在指定日期的价格。"
                "Supports: lithium_carbonate, copper_lme, zinc_lme, nickel_lme, "
                "iron_ore_62pct, gold_lbma, silver_lbma, cobalt_sulfate, rare_earth_ndpr, spodumene_6pct."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "commodity": {
                        "type": "string",
                        "description": "商品名称, e.g. 'lithium_carbonate', '铜', '铜'"
                    },
                    "date": {
                        "type": "string",
                        "description": "日期 YYYY-MM-DD, 默认今天"
                    }
                },
                "required": ["commodity"]
            }
        ),
        Tool(
            name="get_trend",
            description="获取指定商品最近N天的价格走势。Get price trend for last N days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "commodity": {
                        "type": "string",
                        "description": "商品名称"
                    },
                    "days": {
                        "type": "integer",
                        "description": "查询天数, default 30",
                        "default": 30
                    }
                },
                "required": ["commodity"]
            }
        ),
        Tool(
            name="list_commodities",
            description="列出所有支持的商品及当前价格。",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_price":
        return await _handle_get_price(arguments)
    elif name == "get_trend":
        return await _handle_get_trend(arguments)
    elif name == "list_commodities":
        return await _handle_list_commodities()
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_get_price(args: dict) -> list[TextContent]:
    commodity_name = args["commodity"]
    date_str = args.get("date", "2026-05-26")
    key = _resolve_commodity(commodity_name)
    if not key:
        return [TextContent(type="text", text=json.dumps({
            "error": f"Unknown commodity: {commodity_name}",
            "supported": list(BASE_PRICES.keys()),
            "aliases": list(COMMODITY_ALIASES.keys())
        }, ensure_ascii=False, indent=2))]
    return [TextContent(type="text", text=json.dumps(
        _generate_price(key, date_str), ensure_ascii=False, indent=2
    ))]


async def _handle_get_trend(args: dict) -> list[TextContent]:
    commodity_name = args["commodity"]
    days = min(args.get("days", 30), 90)
    key = _resolve_commodity(commodity_name)
    if not key:
        return [TextContent(type="text", text=json.dumps({
            "error": f"Unknown commodity: {commodity_name}"
        }, ensure_ascii=False, indent=2))]
    trend_data = _generate_trend(key, days)
    prices = [d["price"] for d in trend_data]
    summary = {
        "commodity": key,
        "unit": BASE_PRICES[key]["unit"],
        "days": days,
        "start_date": trend_data[0]["date"],
        "end_date": trend_data[-1]["date"],
        "start_price": trend_data[0]["price"],
        "end_price": trend_data[-1]["price"],
        "change_pct": round((trend_data[-1]["price"] - trend_data[0]["price"]) / trend_data[0]["price"] * 100, 2),
        "high": round(max(prices), 2),
        "low": round(min(prices), 2),
        "avg": round(sum(prices) / len(prices), 2),
    }
    return [TextContent(type="text", text=json.dumps({
        "summary": summary, "daily_prices": trend_data
    }, ensure_ascii=False, indent=2))]


async def _handle_list_commodities() -> list[TextContent]:
    today = "2026-05-26"
    commodities = []
    for key, info in BASE_PRICES.items():
        p = _generate_price(key, today)
        commodities.append({"key": key, "unit": info["unit"], "price": p["price"], "date": today})
    return [TextContent(type="text", text=json.dumps(
        {"commodities": commodities}, ensure_ascii=False, indent=2
    ))]


async def main():
    async with stdio_server() as (reader, writer):
        await app.run(reader, writer, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
