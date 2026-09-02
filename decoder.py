from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from eth_abi import decode
from web3 import Web3

from contracts import (
    PAIR_CREATED_V2,
    POOL_CREATED_V3,
    POOL_ALGEBRA,
    MINT_V2,
    MINT_V3,
    INCREASE_LIQ,
    SWAP_V2,
    SWAP_V3,
    ForkType,
    AMM,
    AMM_REGISTRY,
)

log = logging.getLogger("decoder")


@dataclass
class PairCreatedEvent:
    kind: str = "pair_created"
    amm_name: str = ""
    fork: ForkType = ForkType.UNISWAP_V2
    token0: str = ""
    token1: str = ""
    pair_address: str = ""
    pair_index: int = 0
    block_number: int = 0
    tx_hash: str = ""
    log_index: int = 0


@dataclass
class PoolCreatedEvent:
    kind: str = "pool_created"
    amm_name: str = ""
    fork: ForkType = ForkType.UNISWAP_V3
    token0: str = ""
    token1: str = ""
    fee: int = 0
    tick_spacing: int = 0
    pool_address: str = ""
    block_number: int = 0
    tx_hash: str = ""
    log_index: int = 0


@dataclass
class MintEvent:
    kind: str = "mint"
    amm_name: str = ""
    fork: ForkType = ForkType.UNISWAP_V2
    sender: str = ""
    owner: str = ""
    amount0: int = 0
    amount1: int = 0
    token0: str = ""
    token1: str = ""
    pair_address: str = ""
    block_number: int = 0
    tx_hash: str = ""
    log_index: int = 0


@dataclass
class SwapEvent:
    kind: str = "swap"
    amm_name: str = ""
    fork: ForkType = ForkType.UNISWAP_V2
    sender: str = ""
    to: str = ""
    amount0_in: int = 0
    amount1_in: int = 0
    amount0_out: int = 0
    amount1_out: int = 0
    token0: str = ""
    token1: str = ""
    pair_address: str = ""
    block_number: int = 0
    tx_hash: str = ""
    log_index: int = 0


Event = PairCreatedEvent | PoolCreatedEvent | MintEvent | SwapEvent


def _addr_from_topic(topic: bytes | str) -> str:
    if isinstance(topic, str):
        if topic.startswith("0x"):
            topic = topic[2:]
        topic = bytes.fromhex(topic)
    return Web3.to_checksum_address(topic[12:])


def _build_factory_map() -> dict[str, AMM]:
    m: dict[str, AMM] = {}
    for amm in AMM_REGISTRY:
        m[amm.factory.lower()] = amm
        if amm.pool_deployer:
            m[amm.pool_deployer.lower()] = amm
    return m


FACTORY_MAP = _build_factory_map()

TOPIC_TO_EVENTS: dict[str, list[str]] = {
    PAIR_CREATED_V2.lower(): ["pair_created"],
    POOL_CREATED_V3.lower(): ["pool_created"],
    POOL_ALGEBRA.lower(): ["pool_created"],
    MINT_V2.lower(): ["mint"],
    MINT_V3.lower(): ["mint"],
    INCREASE_LIQ.lower(): ["mint"],
    SWAP_V2.lower(): ["swap"],
    SWAP_V3.lower(): ["swap"],
}


def get_watched_topics() -> list[str]:
    return list(TOPIC_TO_EVENTS.keys())


def decode_log(log_entry: dict[str, Any]) -> Event | None:
    try:
        addr = log_entry["address"].lower()
        topics = log_entry["topics"]
        data = log_entry["data"]
        if isinstance(data, str):
            data = bytes.fromhex(data[2:]) if data.startswith("0x") else bytes.fromhex(data)

        topic0 = topics[0].hex() if isinstance(topics[0], (bytes, bytearray)) else topics[0]
        topic0 = topic0.lower()

        amm = FACTORY_MAP.get(addr)
        amm_name = amm.name if amm else "Unknown"
        fork = amm.fork if amm else ForkType.UNISWAP_V2

        block = log_entry.get("blockNumber", 0)
        if isinstance(block, str):
            block = int(block, 16) if block.startswith("0x") else int(block)
        tx = log_entry.get("transactionHash", b"")
        if isinstance(tx, (bytes, bytearray)):
            tx = "0x" + tx.hex()
        log_idx = log_entry.get("logIndex", 0)
        if isinstance(log_idx, str):
            log_idx = int(log_idx, 16) if log_idx.startswith("0x") else int(log_idx)

        if topic0 == PAIR_CREATED_V2.lower():
            return _decode_pair_created_v2(topics, data, amm_name, fork, block, tx, log_idx)
        if topic0 == POOL_CREATED_V3.lower():
            return _decode_pool_created_v3(topics, data, amm_name, fork, block, tx, log_idx)
        if topic0 == POOL_ALGEBRA.lower():
            return _decode_pool_algebra(topics, data, amm_name, fork, block, tx, log_idx)
        if topic0 == MINT_V2.lower():
            return _decode_mint_v2(topics, data, addr, amm_name, fork, block, tx, log_idx)
        if topic0 in (MINT_V3.lower(), INCREASE_LIQ.lower()):
            return _decode_mint_v3(topics, data, addr, amm_name, fork, block, tx, log_idx)
        if topic0 == SWAP_V2.lower():
            return _decode_swap_v2(topics, data, amm_name, fork, block, tx, log_idx)
        if topic0 == SWAP_V3.lower():
            return _decode_swap_v3(topics, data, amm_name, fork, block, tx, log_idx)

        return None
    except Exception as e:
        log.warning("Failed to decode log: %s", e)
        return None


def _decode_pair_created_v2(topics, data, amm_name, fork, block, tx, log_idx) -> PairCreatedEvent:
    token0 = _addr_from_topic(topics[1])
    token1 = _addr_from_topic(topics[2])
    pair_address = _addr_from_topic(topics[3]) if len(topics) > 3 else ""
    if not pair_address:
        # If the pair address wasn't indexed, fall back to decoding from data
        decoded = decode(["address", "uint256"], data)
        pair_address = Web3.to_checksum_address(decoded[0])
    pair_index = 0
    if len(data) >= 32:
        # Uniswap V2 PairCreated data = uint allPairsLength
        pair_index = decode(["uint256"], data)[0]
    return PairCreatedEvent(
        amm_name=amm_name, fork=fork, token0=token0, token1=token1,
        pair_address=pair_address, pair_index=pair_index,
        block_number=block, tx_hash=tx, log_index=log_idx,
    )


def _decode_pool_created_v3(topics, data, amm_name, fork, block, tx, log_idx) -> PoolCreatedEvent:
    token0 = _addr_from_topic(topics[1])
    token1 = _addr_from_topic(topics[2])
    decoded = decode(["uint24", "int24", "address"], data)
    fee = decoded[0]
    tick_spacing = decoded[1]
    pool_address = Web3.to_checksum_address(decoded[2])
    return PoolCreatedEvent(
        amm_name=amm_name, fork=fork, token0=token0, token1=token1,
        fee=fee, tick_spacing=tick_spacing, pool_address=pool_address,
        block_number=block, tx_hash=tx, log_index=log_idx,
    )


def _decode_pool_algebra(topics, data, amm_name, fork, block, tx, log_idx) -> PoolCreatedEvent:
    token0 = _addr_from_topic(topics[1])
    token1 = _addr_from_topic(topics[2])
    pool_address = Web3.to_checksum_address(decode(["address"], data)[0])
    return PoolCreatedEvent(
        amm_name=amm_name, fork=fork, token0=token0, token1=token1,
        fee=0, tick_spacing=0, pool_address=pool_address,
        block_number=block, tx_hash=tx, log_index=log_idx,
    )


def _decode_mint_v2(topics, data, emitter_addr, amm_name, fork, block, tx, log_idx) -> MintEvent:
    sender = _addr_from_topic(topics[1])
    amount0, amount1 = decode(["uint256", "uint256"], data)
    return MintEvent(
        amm_name=amm_name, fork=fork, sender=sender,
        amount0=amount0, amount1=amount1,
        pair_address=Web3.to_checksum_address(emitter_addr),
        block_number=block, tx_hash=tx, log_index=log_idx,
    )


def _decode_mint_v3(topics, data, emitter_addr, amm_name, fork, block, tx, log_idx) -> MintEvent:
    owner = _addr_from_topic(topics[1]) if len(topics) > 1 else ""
    decoded = decode(["uint128", "uint256", "uint256"], data)
    return MintEvent(
        amm_name=amm_name, fork=fork, owner=owner,
        amount0=decoded[1], amount1=decoded[2],
        pair_address=Web3.to_checksum_address(emitter_addr),
        block_number=block, tx_hash=tx, log_index=log_idx,
    )


def _decode_swap_v2(topics, data, amm_name, fork, block, tx, log_idx) -> SwapEvent:
    sender = _addr_from_topic(topics[1])
    decoded = decode(["uint256", "uint256", "uint256", "uint256", "address"], data)
    return SwapEvent(
        amm_name=amm_name, fork=fork, sender=sender,
        amount0_in=decoded[0], amount1_in=decoded[1],
        amount0_out=decoded[2], amount1_out=decoded[3],
        to=Web3.to_checksum_address(decoded[4]),
        block_number=block, tx_hash=tx, log_index=log_idx,
    )


def _decode_swap_v3(topics, data, amm_name, fork, block, tx, log_idx) -> SwapEvent:
    sender = _addr_from_topic(topics[1])
    to = _addr_from_topic(topics[2])
    decoded = decode(["int256", "int256", "uint160", "uint128", "int24"], data)
    amount0 = decoded[0]
    amount1 = decoded[1]
    return SwapEvent(
        amm_name=amm_name, fork=fork, sender=sender, to=to,
        amount0_in=max(0, amount0), amount1_in=max(0, amount1),
        amount0_out=max(0, -amount0), amount1_out=max(0, -amount1),
        block_number=block, tx_hash=tx, log_index=log_idx,
    )
