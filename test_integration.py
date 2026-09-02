"""
Integration tests for decoder/decode using the REAL web3 + eth_abi stack.

Requires: pip install web3 eth-abi
Run:      python test_integration.py
"""

from web3 import Web3
from contracts import (
    AMM_REGISTRY,
    ForkType,
    PAIR_CREATED_V2,
    POOL_CREATED_V3,
    POOL_ALGEBRA,
    MINT_V2,
    MINT_V3,
)
from decoder import decode_log, FACTORY_MAP, get_watched_topics


def topic(addr: str) -> bytes:
    return b"\x00" * 12 + bytes.fromhex(addr[2:])


def dat32(n: int) -> bytes:
    return int(n).to_bytes(32, "big")


def make_log(address, topic0, data=b"", topics_extra=(), block=1000, logidx=1):
    return {
        "address": address,
        "topics": [topic0] + list(topics_extra),
        "data": data,
        "blockNumber": block,
        "logIndex": logidx,
        "transactionHash": b"\xab" * 32,
        "transactionIndex": 0,
        "blockHash": b"\x00" * 32,
        "removed": False,
    }


def test_pair_created_v2_real():
    factory = next(a for a in AMM_REGISTRY if a.name == "HyperSwap V2").factory
    t0, t1, pair = ("0x00000000000000000000000000000000000000aa",
                     "0x00000000000000000000000000000000000000bb",
                     "0x00000000000000000000000000000000000000cc")
    ev = decode_log(make_log(factory, PAIR_CREATED_V2, data=dat32(5),
                             topics_extra=[topic(t0), topic(t1), topic(pair)]))
    assert ev is not None
    assert ev.amm_name == "HyperSwap V2"
    assert ev.token0 == Web3.to_checksum_address(t0) and ev.token1 == Web3.to_checksum_address(t1)
    assert ev.pair_address == Web3.to_checksum_address(pair)
    assert ev.pair_index == 5
    assert ev.block_number == 1000
    print("PASS pair_created_v2:", ev.amm_name, ev.token0, ev.token1)


def test_pool_created_v3_real():
    factory = next(a for a in AMM_REGISTRY if a.name == "HyperSwap V3").factory
    t0, t1, pool = ("0x00000000000000000000000000000000000000aa",
                     "0x00000000000000000000000000000000000000bb",
                     "0x00000000000000000000000000000000000000cc")
    data = Web3.to_bytes(hexstr="0x") + Web3.to_bytes(3).rjust(32, b"\x00") \
        + Web3.to_bytes(60).rjust(32, b"\x00").ljust(62, b"\xff")  # placeholder, overwritten below
    # PoolCreated(address,address,uint24,int24,address) -> fee, tickSpacing, pool
    fee = 3000
    tick_spacing = 60
    data = (fee.to_bytes(32, "big") + tick_spacing.to_bytes(32, "big")
            + Web3.to_bytes(hexstr=pool).rjust(32, b"\x00"))
    ev = decode_log(make_log(factory, POOL_CREATED_V3, data=data,
                             topics_extra=[topic(t0), topic(t1)]))
    assert ev is not None
    assert ev.amm_name == "HyperSwap V3"
    assert ev.token0 == Web3.to_checksum_address(t0) and ev.token1 == Web3.to_checksum_address(t1)
    assert ev.fee == fee and ev.tick_spacing == tick_spacing
    assert ev.pool_address == Web3.to_checksum_address(pool)
    print("PASS pool_created_v3:", ev.amm_name, ev.token0, ev.token1, "fee", ev.fee)


def test_pool_algebra_real():
    factory = next(a for a in AMM_REGISTRY if a.name == "HyperCat").factory
    t0, t1, pool = ("0x0000000000000000000000000000000000000011",
                     "0x0000000000000000000000000000000000000022",
                     "0x0000000000000000000000000000000000000033")
    data = Web3.to_bytes(hexstr=pool).rjust(32, b"\x00")
    ev = decode_log(make_log(factory, POOL_ALGEBRA, data=data,
                             topics_extra=[topic(t0), topic(t1)]))
    assert ev is not None and ev.kind == "pool_created"
    assert ev.amm_name == "HyperCat"
    assert ev.fork == ForkType.ALGEBRA
    assert ev.token0 == Web3.to_checksum_address(t0) and ev.token1 == Web3.to_checksum_address(t1) and ev.pool_address == Web3.to_checksum_address(pool)
    print("PASS pool_algebra:", ev.amm_name, ev.token0, ev.token1)


def test_mint_v2_real():
    # Mint emitted by a pair contract (not a tracked factory) -> amm Unknown
    pair = "0x00000000000000000000000000000000000000aa"
    sender = "0x00000000000000000000000000000000000000bb"
    data = dat32(1000) + dat32(2000)
    ev = decode_log(make_log(pair, MINT_V2, data=data, topics_extra=[topic(sender)]))
    assert ev is not None and ev.kind == "mint"
    assert ev.amount0 == 1000 and ev.amount1 == 2000
    assert ev.pair_address == Web3.to_checksum_address(pair)
    print("PASS mint_v2:", ev.pair_address, ev.amount0, ev.amount1)


def test_topic_identities():
    # Verify the exact known on-chain hashes
    assert PAIR_CREATED_V2.lower() == "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
    assert POOL_CREATED_V3.lower() == "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"
    assert MINT_V2.lower() == "0x4c209b5fc8ad50758f13e2e1088ba56a560dff690a1c6fef26394f4c03821c4f"
    assert MINT_V3.lower() == "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
    topics = get_watched_topics()
    assert len(topics) == len(set(topics)), "duplicate topic0"
    print("PASS topic identities, watched topics:", len(topics))


def test_factory_map_real():
    seen = set()
    for amm in AMM_REGISTRY:
        assert amm.factory.lower() not in seen
        seen.add(amm.factory.lower())
        assert FACTORY_MAP[amm.factory.lower()].name == amm.name
    assert len(seen) == len(AMM_REGISTRY)
    print(f"PASS factory_map: {len(AMM_REGISTRY)} AMMs, {len(seen)} unique factories")


if __name__ == "__main__":
    test_pair_created_v2_real()
    test_pool_created_v3_real()
    test_pool_algebra_real()
    test_mint_v2_real()
    test_topic_identities()
    test_factory_map_real()
    print("\nALL INTEGRATION TESTS PASSED (real web3)")
