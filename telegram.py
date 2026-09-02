from __future__ import annotations

import logging
import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, EXPLORER_BASE_URL
from contracts import ForkType
from decoder import PairCreatedEvent, PoolCreatedEvent, MintEvent, SwapEvent

log = logging.getLogger("telegram")

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["Content-Type"] = "application/json"
    return _session


def _send(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials not set, skipping alert")
        print(text)
        return False
    try:
        resp = _get_session().post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return True
        log.warning("Telegram API error %d: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        log.error("Failed to send Telegram message: %s", e)
        return False


def _tx_link(tx_hash: str) -> str:
    return f"{EXPLORER_BASE_URL}/tx/{tx_hash}"


def _fork_label(fork: ForkType) -> str:
    labels = {
        ForkType.UNISWAP_V2: "V2",
        ForkType.UNISWAP_V3: "V3/CL",
        ForkType.ALGEBRA: "Algebra",
    }
    return labels.get(fork, "?")


def _token_info(w3, address: str) -> tuple[str, int]:
    try:
        from contracts import ERC20_ABI
        contract = w3.eth.contract(
            address=w3.to_checksum_address(address), abi=ERC20_ABI
        )
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        return symbol, decimals
    except Exception:
        return "???", 18


def format_amount(amount: int, decimals: int) -> str:
    if decimals == 0:
        return str(amount)
    value = amount / (10 ** decimals)
    if value >= 1_000_000:
        return f"{value:,.0f}"
    if value >= 1_000:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:.4f}"
    if value >= 0.001:
        return f"{value:.6f}"
    return f"{value:.10f}"


def alert_pair_created(w3, event: PairCreatedEvent) -> bool:
    sym0, dec0 = _token_info(w3, event.token0)
    sym1, dec1 = _token_info(w3, event.token1)

    text = (
        f"<b>🟢 NEW PAIR — {event.amm_name}</b> ({_fork_label(event.fork)})\n\n"
        f"<b>Token A:</b> <code>{event.token0}</code>\n"
        f"  Symbol: {sym0}\n\n"
        f"<b>Token B:</b> <code>{event.token1}</code>\n"
        f"  Symbol: {sym1}\n\n"
        f"<b>Pool:</b> <code>{event.pair_address}</code>\n"
        f"Block: {event.block_number}\n\n"
        f"<a href=\"{_tx_link(event.tx_hash)}\">View TX</a>"
    )
    return _send(text)


def alert_pool_created(w3, event: PoolCreatedEvent) -> bool:
    sym0, dec0 = _token_info(w3, event.token0)
    sym1, dec1 = _token_info(w3, event.token1)

    fee_pct = event.fee / 1_000_000 * 100

    text = (
        f"<b>🟢 NEW POOL — {event.amm_name}</b> ({_fork_label(event.fork)})\n\n"
        f"<b>Token A:</b> <code>{event.token0}</code>\n"
        f"  Symbol: {sym0}\n\n"
        f"<b>Token B:</b> <code>{event.token1}</code>\n"
        f"  Symbol: {sym1}\n\n"
        f"Fee: {fee_pct:.2f}% | Tick: {event.tick_spacing}\n"
        f"<b>Pool:</b> <code>{event.pool_address}</code>\n"
        f"Block: {event.block_number}\n\n"
        f"<a href=\"{_tx_link(event.tx_hash)}\">View TX</a>"
    )
    return _send(text)


def alert_mint(w3, event: MintEvent, pair_info: dict | None = None, token0: str = "", token1: str = "") -> bool:
    token0 = token0 or (pair_info.get("token0", "") if pair_info else "")
    token1 = token1 or (pair_info.get("token1", "") if pair_info else "")

    sym0, dec0 = _token_info(w3, token0) if token0 else ("???", 18)
    sym1, dec1 = _token_info(w3, token1) if token1 else ("???", 18)

    amt0 = format_amount(event.amount0, dec0)
    amt1 = format_amount(event.amount1, dec1)

    pool_addr = event.pair_address or (pair_info.get("pool", "") if pair_info else "")

    text = (
        f"<b>💧 LIQUIDITY ADDED — {event.amm_name}</b> ({_fork_label(event.fork)})\n\n"
    )
    if pool_addr:
        text += f"<b>Pool:</b> <code>{pool_addr}</code>\n"
    if event.sender:
        text += f"Provider: <code>{event.sender}</code>\n"
    if event.owner:
        text += f"Provider: <code>{event.owner}</code>\n"
    text += (
        f"\nAmount A: {amt0} {sym0}\n"
        f"Amount B: {amt1} {sym1}\n"
        f"Block: {event.block_number}\n\n"
    )
    if token0:
        text += f"CA A: <code>{token0}</code>\n"
    if token1:
        text += f"CA B: <code>{token1}</code>\n"
    text += f"\n<a href=\"{_tx_link(event.tx_hash)}\">View TX</a>"
    return _send(text)


def alert_swap(w3, event: SwapEvent, pair_info: dict | None = None) -> bool:
    token0 = pair_info.get("token0", "") if pair_info else ""
    token1 = pair_info.get("token1", "") if pair_info else ""

    sym0, dec0 = _token_info(w3, token0) if token0 else ("???", 18)
    sym1, dec1 = _token_info(w3, token1) if token1 else ("???", 18)

    pool_addr = event.pair_address or (pair_info.get("pool", "") if pair_info else "")

    direction = ""
    if event.amount0_in > 0:
        direction = f"{format_amount(event.amount0_in, dec0)} {sym0} → {format_amount(event.amount1_out, dec1)} {sym1}"
    elif event.amount1_in > 0:
        direction = f"{format_amount(event.amount1_in, dec1)} {sym1} → {format_amount(event.amount0_out, dec0)} {sym0}"

    text = (
        f"<b>🔄 FIRST SWAP — {event.amm_name}</b> ({_fork_label(event.fork)})\n\n"
        f"Pool: <code>{pool_addr}</code>\n"
        f"Trader: <code>{event.sender}</code>\n\n"
        f"Swap: {direction}\n"
        f"Block: {event.block_number}\n\n"
    )
    if token0:
        text += f"CA A: <code>{token0}</code>\n"
    if token1:
        text += f"CA B: <code>{token1}</code>\n"
    text += f"\n<a href=\"{_tx_link(event.tx_hash)}\">View TX</a>"
    return _send(text)


def alert_startup(num_amm: int, last_block: int) -> bool:
    text = (
        f"<b>🚀 HyperEVM Monitor Started</b>\n\n"
        f"Tracking {num_amm} AMMs\n"
        f"Last block: {last_block}\n\n"
        f"Monitoring for:\n"
        f"  • New pair/pool creations\n"
        f"  • Liquidity additions\n"
        f"  • First swaps on new pairs"
    )
    return _send(text)


def alert_error(error: str) -> bool:
    return _send(f"<b>⚠️ Monitor Error</b>\n\n<code>{error[:500]}</code>")


def alert_reconnect(attempts: int) -> bool:
    return _send(f"🔄 Reconnected after {attempts} attempts")
