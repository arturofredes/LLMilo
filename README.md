# LLMilo

Named after Milo, the best dog in the house — LLMilo is an LLM-powered Telegram bot that helps siblings divide and track household chores. Instead of arguing about who was supposed to do the dishes, just ask the bot.

## How it works

LLMilo is a Telegram bot backed by an LLM agent with tool-calling capabilities. When you send a message, the agent decides which tools to call to answer your request — whether that's checking what chores are pending, recording that you cleaned the bathroom, or seeing who's been pulling their weight.

The tools are exposed via an **MCP (Model Context Protocol)** server, so adding new capabilities is as simple as defining a new tool.

### Example conversations

- "What chores are pending?" → Shows all pending chores for the household
- "I just mopped the floor" → Records the action
- "Who has done the most chores this week?" → Queries the action history
- "Add a new weekly chore: take out the trash in the kitchen" → Creates the chore

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `ALLOWED_CHATS` | Comma-separated chat IDs the bot will respond to (leave empty to allow all) |
| `LLM_API_BASE` | Custom API base URL (for OpenAI-compatible providers) |
| `LLM_API_KEY` | API key for the LLM provider |
| `LLM_MODEL` | Model identifier (e.g. `openai/gpt-4o`, `anthropic/claude-sonnet-4-20250514`) |

### 3. Configure your household

Edit the YAML files in `household/`:

- **`household.yaml`** — Define your household, its rooms/areas (elements), and chores with frequency and optional due times
- **`people.yaml`** — Add the people in your household with their names and optional Telegram IDs

### 4. Run the bot

```bash
python -m bot.main
```

## Architecture

```
LLMilo/
├── agent/          # LLM client and agent loop
│   ├── llm.py      # LiteLLM wrapper for chat completions with tool support
│   └── loop.py     # Agentic loop: call LLM → execute tools → repeat
├── bot/            # Telegram bot interface
│   ├── main.py     # Bot startup, MCP client lifecycle
│   └── handler.py  # Message handler with chat history
├── mcp_tools/      # MCP server & client for tool execution
│   ├── server.py   # FastMCP server exposing household tools
│   └── client.py   # MCP client that connects to the server and bridges tools to LiteLLM
├── household/      # Household data & configuration
│   ├── household.yaml
│   └── people.yaml
├── data/           # SQLite database (auto-created)
├── .env.example
└── requirements.txt
```

### Available tools

| Tool | Description |
|---|---|
| `get_household_state` | View people, pending chores, and completed chores |
| `write_action` | Record that a chore was completed by someone |
| `get_history` | Query action history with filters (person, chore, date range) |
| `add_element` | Add a room/area to the household |
| `add_chore` | Add a chore to an element (daily/weekly/biweekly/monthly/yearly) |
| `add_person` | Add a person to the household |
| `remove_element` | Remove a room/area and all its chores |
| `remove_chore` | Remove a specific chore |
| `remove_person` | Remove a person from the household |
| `get_current_time` | Get the current date and time |

## Tech stack

- **Python** + [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- **[LiteLLM](https://github.com/BerriAI/litellm)** for LLM provider abstraction
- **[MCP](https://modelcontextprotocol.io/)** for tool server/client
- **SQLAlchemy** for the persistence layer (SQLite)
