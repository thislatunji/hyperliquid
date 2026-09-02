import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
HYPEREVM_RPC_URL = os.environ.get("HYPEREVM_RPC_URL", "https://rpc.hyperliquid.xyz/evm")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
BLOCKS_PER_POLL = int(os.environ.get("BLOCKS_PER_POLL", "50"))
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

HYPE_USDC_ADDRESS = "0xb8ea8c60d3c78fbc0de8e5e1b119b4c37b2f5e51"
USDC_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"

EXPLORER_BASE_URL = "https://hyperevmscan.io"
