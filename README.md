# HyperEVM New Token Launch Monitor

A Telegram bot that monitors HyperEVM (Hyperliquid's EVM chain) in real time and
notifies you the moment a new token pair is created or liquidity is added across
all supported AMMs.

## What It Detects

| Event | When you get notified |
|---|---|
| 🟢 **New Pair / Pool** | A new trading pair/pool is created on any tracked AMM |
| 💧 **Liquidity Added** | Someone adds liquidity (Mint/IncreaseLiquidity) to a pair |
| 🔄 **First Swap** | The first swap happens on a newly created pair |

Each alert includes the **token contract addresses (CAs)** for easy copy-paste,
the AMM name, liquidity amounts, and a block-explorer link to the transaction.

## Supported AMMs

**V2 / UniswapV2-style:** HyperSwap V2 · Laminar V2 · KittenSwap · HyperTrade V2 · Hybra V2

**V3 / CL-style:** HyperSwap V3 · Laminar V3 · HyperTrade V3 · Hybra CL · Ramses

**Algebra-style:** HyperCat · Nest · Liquidity

> ManaSwap, DyoSwap, UltraSolid, Funnel, Turbo and ProjectX factory addresses are
> not yet confirmed — add them to `AMM_REGISTRY` in `contracts.py` once verified.

## Requirements

- Python 3.10+
- `pip install -r requirements.txt` (web3, eth-abi, requests, python-dotenv)

## Setup

1. **Get a Telegram bot token** — message [@BotFather](https://t.me/BotFather)
   on Telegram, send `/newbot`, and copy the token it gives you.

2. **Get your chat ID** — message your new bot, then open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and copy the
   numeric `chat.id` value.

3. **Configure the environment:**
   ```bash
   cp .env.example .env
   # edit .env and fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
   ```

4. **Run the monitor:**
   ```bash
   python monitor.py
   ```

That's it — you'll get a "🚀 HyperEVM Monitor Started" message in Telegram, then
real-time alerts as events occur.

## Configuration (.env)

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Your bot token (required) |
| `TELEGRAM_CHAT_ID` | — | Destination chat ID (required) |
| `HYPEREVM_RPC_URL` | `https://rpc.hyperliquid.xyz/evm` | RPC endpoint |
| `POLL_INTERVAL_SECONDS` | `3` | How often to poll (seconds) |
| `BLOCKS_PER_POLL` | `50` | Max blocks scanned per poll |
| `STATE_FILE` | `state.json` | Local state persistence path |

## How It Works

1. On startup it records the current block as the baseline.
2. Every few seconds it calls `eth_getLogs` on the confirmed AMM factory
   addresses, filtering for:
   - `PairCreated` (V2), `PoolCreated` (V3), `Pool` (Algebra) — new pairs
   - `Mint` / `IncreaseLiquidity` — liquidity additions
   - `Swap` on newly created pairs — first-swap detection
3. It decodes the logs, resolves token symbols/decimals, and sends a formatted
   Telegram alert.
4. Event IDs and the last scanned block are persisted to `state.json`, so
   restarts resume without missing data or sending duplicate alerts.

The official HyperEVM RPC does not expose WebSocket `eth_subscribe`, so the bot
uses efficient HTTP log polling — no third-party RPC key required.

## Testing

The decoder logic is covered by self-contained unit tests that don't need
network access or the real `web3` package:

```bash
python test_decoder.py
```

## Adding an AMM

Add an entry to `AMM_REGISTRY` in `contracts.py` with the AMM name, its
checksummed factory address, and fork type:

```python
AMM("MySwap", "0xChecksummedFactoryAddress", ForkType.UNISWAP_V2)
```

Supported forks: `ForkType.UNISWAP_V2`, `ForkType.UNISWAP_V3`, `ForkType.ALGEBRA`.
