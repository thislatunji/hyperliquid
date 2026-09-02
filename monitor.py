from __future__ import annotations

import asyncio
import logging
import os
import signal
import ssl

from web3 import AsyncWeb3, AsyncHTTPProvider

from config import (
    HYPEREVM_RPC_URL,
    POLL_INTERVAL,
    BLOCKS_PER_POLL,
)
from contracts import AMM_REGISTRY, ForkType
from decoder import (
    get_watched_topics,
    decode_log,
    PairCreatedEvent,
    PoolCreatedEvent,
    MintEvent,
    SwapEvent,
)
from state import MonitorState, load_state, save_state
import telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("monitor")

running = True


def _signal_handler(sig, frame):
    global running
    log.info("Signal %s received, shutting down...", sig)
    running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


async def resolve_pair_tokens(w3: AsyncWeb3, pair_address: str) -> tuple[str, str]:
    """For a V2 pair address, resolve token0/token1 via eth_call."""
    try:
        from contracts import PAIR_ABI
        contract = w3.eth.contract(
            address=w3.to_checksum_address(pair_address), abi=PAIR_ABI
        )
        t0 = await contract.functions.token0().call()
        t1 = await contract.functions.token1().call()
        return t0, t1
    except Exception:
        return "", ""


async def scan_block_range(w3, state: MonitorState, from_block: int, to_block: int) -> None:
    if from_block > to_block:
        return

    all_addresses = []
    for amm in AMM_REGISTRY:
        all_addresses.append(amm.factory)
        if amm.pool_deployer:
            all_addresses.append(amm.pool_deployer)
    all_addresses = [w3.to_checksum_address(a) for a in all_addresses]

    topics = get_watched_topics()

    try:
        logs = await w3.eth.get_logs(
            {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": all_addresses,
                # All our topics are event-signature hashes, so they all filter on
                # position 0. Nest them as an OR-list; passing them as separate
                # position elements exceeds HyperEVM's max-topics-per-request cap.
                "topics": [topics],
            }
        )
    except Exception as e:
        log.warning("get_logs failed for %d-%d: %s", from_block, to_block, e)
        return

    if not logs:
        return

    for log_entry in sorted(logs, key=lambda l: (int(l.get("blockNumber", 0), 16), int(l.get("logIndex", 0), 16))):
        event = decode_log(log_entry)
        if event is None:
            continue

        await process_event(w3, state, event)


async def process_event(w3: AsyncWeb3, state: MonitorState, event) -> None:
    try:
        if isinstance(event, PairCreatedEvent):
            await handle_pair_created(w3, state, event)
        elif isinstance(event, PoolCreatedEvent):
            await handle_pool_created(w3, state, event)
        elif isinstance(event, MintEvent):
            await handle_mint(w3, state, event)
        elif isinstance(event, SwapEvent):
            await handle_swap(w3, state, event)
    except Exception as e:
        log.error("Error processing event: %s", e)


async def handle_pair_created(w3, state, event: PairCreatedEvent) -> None:
    key = state.pair_key(event.token0, event.token1)
    pair_addr = event.pair_address

    log.info(
        "NEW PAIR [%s]: %s / %s -> %s (block %d)",
        event.amm_name, event.token0, event.token1, pair_addr, event.block_number,
    )

    state.mark_known(key, event.token0, event.token1, event.amm_name, pair_addr)
    telegram.alert_pair_created(w3, event)
    save_state(state)


async def handle_pool_created(w3, state, event: PoolCreatedEvent) -> None:
    key = state.pair_key(event.token0, event.token1)

    log.info(
        "NEW POOL [%s]: %s / %s (fee %d) -> %s (block %d)",
        event.amm_name, event.token0, event.token1, event.fee, event.pool_address,
        event.block_number,
    )

    state.mark_known(key, event.token0, event.token1, event.amm_name, event.pool_address)
    telegram.alert_pool_created(w3, event)
    save_state(state)


async def handle_mint(w3, state, event: MintEvent) -> None:
    token0, token1 = event.token0, event.token1
    if event.fork in (ForkType.UNISWAP_V2,) and not token0:
        token0, token1 = await resolve_pair_tokens(w3, event.pair_address)

    pair_key = state.pair_key(token0, token1) if token0 and token1 else None
    pair_info = state.known_pairs.get(pair_key) if pair_key else None

    log.info(
        "LIQUIDITY [%s]: amt0=%s amt1=%s pair=%s (block %d)",
        event.amm_name, event.amount0, event.amount1, event.pair_address, event.block_number,
    )

    telegram.alert_mint(w3, event, pair_info, token0=token0, token1=token1)


async def handle_swap(w3, state, event: SwapEvent) -> None:
    key = state.pair_key(event.token0, event.token1) if event.token0 and event.token1 else None
    if key is None or not state.is_new_this_session(key):
        return

    if not state.is_known(key):
        return

    pair_info = state.known_pairs.get(key)
    log.info(
        "FIRST SWAP [%s]: on pair %s (block %d)",
        event.amm_name, key, event.block_number,
    )
    telegram.alert_swap(w3, event, pair_info)


async def run(w3: AsyncWeb3, state: MonitorState) -> None:
    global running

    if state.last_block == 0:
        state.last_block = await w3.eth.block_number
        log.info("Startup: starting from latest block %d", state.last_block)
        save_state(state)
    else:
        want = state.last_block + 1
        latest = await w3.eth.block_number
        log.info(
            "Resuming from block %d (latest is %d, %.2f block gap)",
            want, latest, latest - state.last_block,
        )
        if want <= latest:
            await scan_block_range(w3, state, want, latest)

    while running:
        try:
            latest = await w3.eth.block_number
            if latest > state.last_block:
                to_block = min(latest, state.last_block + BLOCKS_PER_POLL)
                await scan_block_range(w3, state, state.last_block + 1, to_block)
                state.last_block = to_block
                save_state(state)

            await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("Polling error: %s", e)
            telegram.alert_error(str(e))
            await asyncio.sleep(POLL_INTERVAL * 5)


def _build_w3() -> AsyncWeb3:
    """Build the AsyncWeb3 client with a CA-bundle that works on macOS.

    The python.org macOS Python build fails to find the system CA store, which
    makes aiohttp (used by AsyncHTTPProvider) raise CERTIFICATE_VERIFY_FAILED,
    even though `requests` works. We supply certifi's CA bundle explicitly.
    """
    request_kwargs: dict = {"timeout": 30}
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        request_kwargs["ssl"] = ctx
    except Exception:
        log.warning("certifi not available; relying on system CA store")
    return AsyncWeb3(AsyncHTTPProvider(HYPEREVM_RPC_URL, request_kwargs=request_kwargs))


async def main() -> None:
    state = load_state()

    w3 = _build_w3()
    try:
        latest = await w3.eth.block_number
    except Exception as e:
        log.error("Could not connect to RPC at %s: %s", HYPEREVM_RPC_URL, e)
        raise SystemExit(1)

    log.info("Connected to HyperEVM, latest block %d", latest)
    log.info("Monitoring %d AMMs: %s", len(AMM_REGISTRY), ", ".join(a.name for a in AMM_REGISTRY))

    telegram.alert_startup(len(AMM_REGISTRY), state.last_block if state.last_block else latest)

    await run(w3, state)
    log.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
