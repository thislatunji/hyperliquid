"""
Standalone unit tests for decoder logic.

These tests stub out `web3` and `eth_abi` so they run WITHOUT network access
and without the real web3 package installed. Requires only `pytest`.
"""

import sys
import types

# --- Stub web3 before importing decoder ---
_stub_web3 = types.ModuleType("web3")
_stub_abi = types.ModuleType("eth_abi")
_stub_decode = types.ModuleType("eth_abi.decode")


class _W3:
    @staticmethod
    def keccak(text=None, primative=None):
        raise NotImplementedError("stub")

    @staticmethod
    def to_checksum_address(a):
        if isinstance(a, (bytes, bytearray)):
            return "0x" + bytes(a).hex()
        s = a.lower()
        return s if s.startswith("0x") else "0x" + s


def _keccak_stub(text=None, primative=None):
    # Keccak256 via hashlib sha3_256 is NOT keccak. We provide a tiny pure-
    # python keccak fallback so topic hashes are computed identically to real.
    import struct

    def keccak_f_1600(state):
        R, M = 24, 0xFFFFFFFFFFFFFFFF
        RC = [
            0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
            0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
            0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
            0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
            0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
            0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
            0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
            0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
        ]
        ROT = [
            [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
            [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
        ]

        def rol(x, n):
            return ((x << n) | (x >> (64 - n))) & M

        for rc in RC:
            c = [state[x * 5] ^ state[x * 5 + 1] ^ state[x * 5 + 2]
                 ^ state[x * 5 + 3] ^ state[x * 5 + 4] for x in range(5)]
            d = [c[(x - 1) % 5] ^ rol(c[(x + 1) % 5], 1) for x in range(5)]
            for y in range(5):
                for x in range(5):
                    state[5 * x + y] ^= d[x]
            b = [0] * 25
            for y in range(5):
                for x in range(5):
                    b[5 * ((2 * x + 3 * y) % 5) + y] = rol(state[5 * y + x], ROT[x][y])
            for x in range(5):
                for y in range(5):
                    state[5 * y + x] = b[5 * x + y] ^ (
                        (~b[5 * (x + 1) % 5 + y]) & b[5 * (x + 2) % 5 + y]
                    )
            state[0] ^= rc
        return state

    r = 168  # rate for keccak-256
    data = primative if primative is not None else text
    if isinstance(data, str):
        data = data.encode()
    data = bytearray(data)
    data += b"\x01" if len(data) % r == r - 1 else b"\x01"
    rate_bytes = r // 8
    data += b"\x80"
    data += b"\x00" * (rate_bytes - (len(data) % rate_bytes))
    state = [0] * 25
    for block_i in range(0, len(data), rate_bytes):
        block = data[block_i:block_i + rate_bytes]
        for i, chunk in enumerate(
            [block[j:j + 8] for j in range(0, rate_bytes, 8)]
        ):
            state[i] ^= int.from_bytes(chunk.ljust(8, b"\x00"), "little")
        state = keccak_f_1600(state)
    out = b"".join(x.to_bytes(8, "little") for x in state[:4])
    return out


_w3 = _W3()
_w3.keccak = _keccak_stub

def _checksum(a):
    if isinstance(a, (bytes, bytearray)):
        return "0x" + bytes(a).hex()
    s = a.lower()
    return s if s.startswith("0x") else "0x" + s


_w3.to_checksum_address = _checksum
_stub_web3.Web3 = _w3


def _decode_stub(types_list, data_bytes):
    idx = 0
    out = []
    for t in types_list:
        size = 32
        if t == "address":
            val = "0x" + data_bytes[idx + 12:idx + 32].hex()
            val = val.lower()
        elif "uint" in t or t == "int24" or t == "uint24" or t == "int256":
            raw = data_bytes[idx:idx + 32]
            if t.startswith("int"):
                val = int.from_bytes(raw, "big", signed=True)
            else:
                val = int.from_bytes(raw, "big")
        else:
            raise ValueError(t)
        out.append(val)
        idx += size
    return out


_stub_abi.decode = _decode_stub
_stub_decode.decode = _decode_stub

sys.modules["web3"] = _stub_web3
sys.modules["eth_abi"] = _stub_abi
sys.modules["eth_abi.decode"] = _stub_decode

# --- Now import decoder + contracts ---
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from contracts import (
    PAIR_CREATED_V2,
    MINT_V2,
    MINT_V3,
    POOL_ALGEBRA,
    ForkType,
)
from decoder import decode_log, get_watched_topics, AMM_REGISTRY, FACTORY_MAP


def _topic(addr: str) -> str:
    return "0x" + "00" * 12 + addr.lower()[2:]


def _log(factory_addr, topic0, data_hex="0x", topics_extra=(), block=1000, logidx=0, tx=b"\xab" * 32):
    topics = [topic0] + [t for t in topics_extra]
    return {
        "address": factory_addr,
        "topics": topics,
        "data": data_hex,
        "blockNumber": block,
        "logIndex": logidx,
        "transactionHash": tx,
        "transactionIndex": 0,
        "blockHash": b"\x00" * 32,
        "removed": False,
    }


def test_pair_created_v2():
    amm = next(a for a in AMM_REGISTRY if a.name == "HyperSwap V2")
    t0, t1, pair = "0x00000000000000000000000000000000000000aa", \
                   "0x00000000000000000000000000000000000000bb", \
                   "0x00000000000000000000000000000000000000cc"
    data = (int(5).to_bytes(32, "big"))
    ev = decode_log(_log(amm.factory, PAIR_CREATED_V2, data_hex="0x" + data.hex(),
                         topics_extra=[_topic(t0), _topic(t1), _topic(pair)]))
    assert ev is not None
    assert ev.kind == "pair_created"
    assert ev.amm_name == "HyperSwap V2"
    assert ev.token0 == t0
    assert ev.token1 == t1
    assert ev.pair_address == pair
    assert ev.block_number == 1000
    print("test_pair_created_v2 OK")


def test_pool_algebra():
    amm = next(a for a in AMM_REGISTRY if a.name == "HyperCat")
    t0, t1, pool = "0x00000000000000000000000000000000000000dd", \
                   "0x00000000000000000000000000000000000000ee", \
                   "0x00000000000000000000000000000000000000ff"
    data = (int(pool, 16)).to_bytes(32, "big")
    ev = decode_log(_log(amm.factory, POOL_ALGEBRA, data_hex="0x" + data.hex(),
                         topics_extra=[_topic(t0), _topic(t1)]))
    assert ev is not None
    assert ev.kind == "pool_created"
    assert ev.amm_name == "HyperCat"
    assert ev.token0 == t0 and ev.token1 == t1 and ev.pool_address == pool
    print("test_pool_algebra OK")


def test_mint_v2_pair_address():
    t0, t1 = "0x0000000000000000000000000000000000000011", \
             "0x0000000000000000000000000000000000000022"
    sender = "0x0000000000000000000000000000000000000033"
    data = (int(1000).to_bytes(32, "big") + int(2000).to_bytes(32, "big"))
    # Mint emitted by the pair contract (which we don't track), so amm = Unknown
    ev = decode_log(_log(t0, MINT_V2, data_hex="0x" + data.hex(),
                         topics_extra=[_topic(sender)]))
    assert ev is not None
    assert ev.kind == "mint"
    assert ev.amount0 == 1000 and ev.amount1 == 2000
    assert ev.pair_address == t0  # emitter is the pair
    print("test_mint_v2_pair_address OK")


def test_known_topic_hashes():
    topics = get_watched_topics()
    assert PAIR_CREATED_V2 in topics
    assert MINT_V2 in topics
    assert MINT_V3 in topics
    assert POOL_ALGEBRA in topics
    assert len(topics) == len(set(topics)), "duplicate topic0 detected"
    print("test_known_topic_hashes OK, topics:", len(topics))


def test_factory_map_length():
    from web3 import Web3
    # ensure every AMM factory maps back to itself
    seen_addr = set()
    for amm in AMM_REGISTRY:
        assert amm.factory.lower() not in seen_addr, f"duplicate address {amm.factory}"
        seen_addr.add(amm.factory.lower())
        assert FACTORY_MAP[amm.factory.lower()].name == amm.name
    assert len(seen_addr) == len(AMM_REGISTRY)
    print(f"test_factory_map_length OK, {len(AMM_REGISTRY)} AMMs, {len(seen_addr)} unique factories")


if __name__ == "__main__":
    test_pair_created_v2()
    test_pool_algebra()
    test_mint_v2_pair_address()
    test_known_topic_hashes()
    test_factory_map_length()
    print("\nAll decoder tests passed")
