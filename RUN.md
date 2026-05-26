# 矿权日报 Agent — 5 分钟快速启动指南

## 项目概述

基于 MCP (Model Context Protocol) 的矿权日报 Agent, 包含:

| 组件 | 说明 |
|------|------|
| `mining-news-mcp` | 矿业新闻聚合 — `search(query, days)` / `fetch_article(url)` |
| `mineral-pdf-mcp` | NI 43-101 储量抽取 — `extract_resources(pdf_url)` / `list_available_reports()` |
| `lme-price-mcp` | 价格行情 — `get_price(commodity, date)` / `get_trend(commodity, days)` |
| Agent Client | ReAct 编排引擎, 协调 3 个 MCP server 生成 Markdown 简报 |

## 方式一: 本地运行 (推荐, < 2 分钟)

```bash
# 1. 安装依赖
cd mining-agent
pip install -r requirements.txt

# 2. 运行 Agent (Demo 模式, 无需 API Key)
python agent/orchestrator.py "给我生成一份关于 Pilbara 锂矿的今日简报"

# 3. (可选) 使用 LLM ReAct 模式
export ANTHROPIC_API_KEY="your-api-key"
python agent/orchestrator.py "生成一份铜矿市场简报"

# 输出: briefing_output.md (Markdown 简报)
```

## 方式二: Docker 运行

```bash
cd mining-agent

# Demo 模式
docker compose run --rm agent "给我生成一份关于 Pilbara 锂矿的今日简报"

# LLM 模式
ANTHROPIC_API_KEY="sk-xxx" docker compose run --rm -e ANTHROPIC_API_KEY agent
```

## 方式三: 接入 Claude Desktop

将 `mcp-config.json` 复制到 Claude Desktop 配置:

```bash
# macOS
cp mcp-config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows
copy mcp-config.json %APPDATA%\Claude\claude_desktop_config.json
```

重启 Claude Desktop 后即可在对话中直接调用 MCP 工具。

## 架构

```
用户输入: "生成 Pilbara 锂矿简报"
         │
         ▼
┌─────────────────────────────────┐
│  Agent Client (ReAct Loop)      │
│  agent/orchestrator.py          │
│                                 │
│  1. 解析意图 → 确定关键词/商品   │
│  2. 并行调用 3 个 MCP Server    │
│  3. 汇总数据 → 生成 Markdown    │
└──────┬──────┬──────┬───────────┘
       │      │      │
       ▼      ▼      ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│mining-   │ │mineral-  │ │lme-price │
│news-mcp  │ │pdf-mcp   │ │-mcp      │
│          │ │          │ │          │
│search()  │ │extract_  │ │get_price │
│fetch_    │ │resources │ │get_trend │
│article() │ │()        │ │()        │
└──────────┘ └──────────┘ └──────────┘
     │            │            │
     ▼            ▼            ▼
 Mock News    Mock NI      Mock LME
 Database     43-101 Data  Price Data
```

## 文件结构

```
mining-agent/
├── agent/
│   ├── __init__.py
│   └── orchestrator.py      # Agent 编排引擎 (ReAct + Demo模式)
├── servers/
│   ├── mining_news_mcp/
│   │   └── server.py        # 新闻 MCP Server
│   ├── mineral_pdf_mcp/
│   │   └── server.py        # PDF储量 MCP Server
│   └── lme_price_mcp/
│       └── server.py        # 价格 MCP Server
├── data/                    # (可选) 数据文件
├── mcp-config.json          # Claude Desktop 配置
├── docker-compose.yml       # Docker 编排
├── Dockerfile
├── requirements.txt
└── RUN.md                   # 本文件
```

## 示例输出

运行后会生成 `briefing_output.md`, 包含:
- **今日新闻摘要** — 近 7 天相关新闻 (标题/来源/链接/摘要)
- **储量与资源数据** — NI 43-101 表格 (Proven/Probable Reserves + M/I/I Resources)
- **价格走势** — 30 天价格变动 + ASCII 趋势图
- **风险提示** — 价格波动/政策/ESG 风险标注
- **信息来源** — 所有引用源链接

## Demo 数据覆盖

| 数据类型 | 覆盖范围 |
|----------|----------|
| 新闻 | 锂矿 (Pilbara/Liontown/Ganfeng/SQM/Rio/政策) + 铜 + 稀土 + 铁矿石 |
| 储量 | Pilbara Minerals (锂), Newmont (金铜), Barrick (金) |
| 价格 | 碳酸锂/氢氧化锂/锂辉石/铜/锌/镍/铁矿石/黄金/白银/钴/稀土 |
