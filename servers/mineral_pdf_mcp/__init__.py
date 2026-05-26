"""
Mineral PDF MCP Server — NI 43-101 储量数据抽取
Tools: extract_resources(pdf_url)
"""

import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Mock NI 43-101 reserve/resource data ───────────────────────────
# Simulates PDF extraction results from real NI 43-101 technical reports

MOCK_PDF_DATA = {
    "https://www.newmont.com/investors/43-101-boddington-2025.pdf": {
        "report_name": "NI 43-101 Technical Report — Boddington Gold Mine, Western Australia",
        "company": "Newmont Corporation",
        "effective_date": "2025-12-31",
        "qualified_person": "Dr. James Whitfield, FAusIMM",
        "mineral_reserves": {
            "proven": {
                "ore_tonnes_mt": 147.2,
                "gold_grade_gpt": 0.68,
                "copper_grade_pct": 0.12,
                "contained_gold_moz": 3.22,
                "contained_copper_kt": 177
            },
            "probable": {
                "ore_tonnes_mt": 283.5,
                "gold_grade_gpt": 0.61,
                "copper_grade_pct": 0.11,
                "contained_gold_moz": 5.56,
                "contained_copper_kt": 312
            },
            "total": {
                "ore_tonnes_mt": 430.7,
                "gold_grade_gpt": 0.63,
                "copper_grade_pct": 0.11,
                "contained_gold_moz": 8.78,
                "contained_copper_kt": 489
            }
        },
        "mineral_resources": {
            "measured": {
                "ore_tonnes_mt": 210.3,
                "gold_grade_gpt": 0.62,
                "copper_grade_pct": 0.10
            },
            "indicated": {
                "ore_tonnes_mt": 425.8,
                "gold_grade_gpt": 0.55,
                "copper_grade_pct": 0.09
            },
            "inferred": {
                "ore_tonnes_mt": 180.5,
                "gold_grade_gpt": 0.48,
                "copper_grade_pct": 0.07
            }
        }
    },
    "https://www.barrick.com/investors/43-101-carlin-2025.pdf": {
        "report_name": "NI 43-101 Technical Report — Carlin Complex, Nevada, USA",
        "company": "Barrick Gold Corporation",
        "effective_date": "2025-11-15",
        "qualified_person": "Dr. Sarah Mitchell, P.Geo",
        "mineral_reserves": {
            "proven": {
                "ore_tonnes_mt": 45.6,
                "gold_grade_gpt": 4.52,
                "contained_gold_moz": 6.63
            },
            "probable": {
                "ore_tonnes_mt": 78.3,
                "gold_grade_gpt": 3.85,
                "contained_gold_moz": 9.69
            },
            "total": {
                "ore_tonnes_mt": 123.9,
                "gold_grade_gpt": 4.10,
                "contained_gold_moz": 16.32
            }
        },
        "mineral_resources": {
            "measured": {
                "ore_tonnes_mt": 89.2,
                "gold_grade_gpt": 3.91
            },
            "indicated": {
                "ore_tonnes_mt": 156.7,
                "gold_grade_gpt": 3.42
            },
            "inferred": {
                "ore_tonnes_mt": 95.3,
                "gold_grade_gpt": 2.85
            }
        }
    },
    "https://www.pilbaraminerals.com.au/investors/43-101-pilgangoora-2025.pdf": {
        "report_name": "NI 43-101 Technical Report — Pilgangoora Lithium-Tantalum Project, WA",
        "company": "Pilbara Minerals Limited",
        "effective_date": "2025-10-01",
        "qualified_person": "Mr. David O'Connor, MAusIMM",
        "mineral_reserves": {
            "proven": {
                "ore_tonnes_mt": 68.5,
                "li2o_grade_pct": 1.26,
                "ta2o5_grade_ppm": 122,
                "contained_lio2_kt": 863,
                "contained_ta2o5_klb": 184
            },
            "probable": {
                "ore_tonnes_mt": 64.2,
                "li2o_grade_pct": 1.18,
                "ta2o5_grade_ppm": 116,
                "contained_lio2_kt": 758,
                "contained_ta2o5_klb": 164
            },
            "total": {
                "ore_tonnes_mt": 132.7,
                "li2o_grade_pct": 1.22,
                "ta2o5_grade_ppm": 119,
                "contained_lio2_kt": 1621,
                "contained_ta2o5_klb": 348
            }
        },
        "mineral_resources": {
            "measured": {
                "ore_tonnes_mt": 108.9,
                "li2o_grade_pct": 1.24,
                "ta2o5_grade_ppm": 120
            },
            "indicated": {
                "ore_tonnes_mt": 98.5,
                "li2o_grade_pct": 1.15,
                "ta2o5_grade_ppm": 113
            },
            "inferred": {
                "ore_tonnes_mt": 73.2,
                "li2o_grade_pct": 1.02,
                "ta2o5_grade_ppm": 98
            }
        }
    },
    "https://www.pilbaraminerals.com.au/investors/pilgangoora-resource-update-2026.pdf": {
        "report_name": "NI 43-101 Technical Report — Pilgangoora Resource Update 2026",
        "company": "Pilbara Minerals Limited",
        "effective_date": "2026-04-15",
        "qualified_person": "Mr. David O'Connor, MAusIMM",
        "mineral_reserves": {
            "proven": {
                "ore_tonnes_mt": 82.3,
                "li2o_grade_pct": 1.29,
                "ta2o5_grade_ppm": 125,
                "contained_lio2_kt": 1062,
                "contained_ta2o5_klb": 227
            },
            "probable": {
                "ore_tonnes_mt": 76.8,
                "li2o_grade_pct": 1.21,
                "ta2o5_grade_ppm": 119,
                "contained_lio2_kt": 929,
                "contained_ta2o5_klb": 201
            },
            "total": {
                "ore_tonnes_mt": 159.1,
                "li2o_grade_pct": 1.25,
                "ta2o5_grade_ppm": 122,
                "contained_lio2_kt": 1991,
                "contained_ta2o5_klb": 428
            }
        },
        "mineral_resources": {
            "measured": {
                "ore_tonnes_mt": 125.4,
                "li2o_grade_pct": 1.27,
                "ta2o5_grade_ppm": 123
            },
            "indicated": {
                "ore_tonnes_mt": 112.8,
                "li2o_grade_pct": 1.18,
                "ta2o5_grade_ppm": 115
            },
            "inferred": {
                "ore_tonnes_mt": 85.6,
                "li2o_grade_pct": 1.04,
                "ta2o5_grade_ppm": 101
            }
        }
    }
}


KNOWN_URLS = list(MOCK_PDF_DATA.keys())

# ── MCP Server ─────────────────────────────────────────────────────
app = Server("mineral-pdf-mcp")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="extract_resources",
            description=(
                "从 NI 43-101 技术报告 PDF 中提取 Indicated Resources 和 Inferred Resources 数据, "
                "包括: 矿石量(Mt), 品位(g/t Au 或 % Cu/Li2O), 金属量(oz Au 或 kt Li2O/t Ta2O5)。"
                "Extract Indicated and Inferred mineral resources from NI 43-101 PDF reports."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_url": {
                        "type": "string",
                        "description": "NI 43-101 PDF 报告的 URL"
                    }
                },
                "required": ["pdf_url"]
            }
        ),
        Tool(
            name="list_available_reports",
            description="列出所有可用的 NI 43-101 报告及其公司和日期。List all available NI 43-101 reports.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "extract_resources":
        return await _extract_resources(arguments)
    elif name == "list_available_reports":
        return await _list_reports()
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _extract_resources(args: dict) -> list[TextContent]:
    pdf_url = args["pdf_url"]
    data = MOCK_PDF_DATA.get(pdf_url)

    if not data:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": f"No data available for URL: {pdf_url}",
                "available_urls": KNOWN_URLS,
                "hint": "Use list_available_reports to see known reports, or provide a URL matching one of the known reports."
            }, ensure_ascii=False, indent=2)
        )]

    return [TextContent(
        type="text",
        text=json.dumps({
            "report_name": data["report_name"],
            "company": data["company"],
            "effective_date": data["effective_date"],
            "qualified_person": data["qualified_person"],
            "mineral_reserves": data["mineral_reserves"],
            "mineral_resources": data["mineral_resources"],
            "exploration_upside": (
                "Significant exploration potential exists along strike and at depth. "
                "Additional drilling recommended for inferred-to-indicated resource conversion."
            ),
            "risks_noted": [
                "Commodity price volatility may impact reserve cutoff grades",
                "Water management requires ongoing monitoring",
                "Community agreements require periodic review"
            ]
        }, ensure_ascii=False, indent=2)
    )]


async def _list_reports() -> list[TextContent]:
    reports = []
    for url, data in MOCK_PDF_DATA.items():
        reports.append({
            "url": url,
            "report_name": data["report_name"],
            "company": data["company"],
            "effective_date": data["effective_date"]
        })
    return [TextContent(
        type="text",
        text=json.dumps({"reports": reports}, ensure_ascii=False, indent=2)
    )]


async def main():
    async with stdio_server() as (reader, writer):
        await app.run(reader, writer, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
