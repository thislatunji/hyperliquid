from web3 import Web3
from enum import Enum


class ForkType(Enum):
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    ALGEBRA = "algebra"


class AMM:
    def __init__(self, name: str, factory: str, fork: ForkType, pool_deployer: str = None):
        self.name = name
        self.factory = Web3.to_checksum_address(factory)
        self.fork = fork
        self.pool_deployer = Web3.to_checksum_address(pool_deployer) if pool_deployer else None


AMM_REGISTRY: list[AMM] = [
    # ── V2-style (PairCreated event) ──────────────────────────────
    AMM("HyperSwap V2", "0x4df039804873717bff7d03694fb941cf0469b79e", ForkType.UNISWAP_V2),
    AMM("Laminar V2", "0x8f45c2143a875de1e31b1c3f523b4c6529e11615", ForkType.UNISWAP_V2),
    AMM("KittenSwap", "0xDa12F450580A4cc485C3b501BAB7b0B3cbc3B31B", ForkType.UNISWAP_V2),
    AMM("HyperTrade V2", "0x4B6AC7503d3FD79CE23D7AE463D14aAAF07F6573", ForkType.UNISWAP_V2),
    AMM("Hybra V2", "0x9c7397c9C5ecC400992843408D3A283fE9108009", ForkType.UNISWAP_V2),

    # NOTE: The following AMMs are known to exist on HyperEVM but their
    # factory addresses have not been confirmed yet. Uncomment and fill in
    # the correct checksummed factory address when verified:
    # AMM("ManaSwap", "0x...", ForkType.UNISWAP_V2),
    # AMM("DyoSwap", "0x...", ForkType.UNISWAP_V2),
    # AMM("UltraSolid", "0x...", ForkType.UNISWAP_V2),
    # AMM("Funnel", "0x...", ForkType.UNISWAP_V2),
    # AMM("Turbo", "0x...", ForkType.UNISWAP_V2),

    # ── V3 / CL-style (PoolCreated event) ─────────────────────────
    AMM("HyperSwap V3", "0xB1c0fa0B789320044A6F623cFe5eBda9562602E3", ForkType.UNISWAP_V3),
    AMM("Laminar V3", "0x40059a6f242c3de0e639693973004921b04d96ad", ForkType.UNISWAP_V3),
    AMM("HyperTrade V3", "0x1Cd8363DfAdA19911f745BA984fce02b42c943bF", ForkType.UNISWAP_V3),
    AMM("Hybra CL", "0x2dC0Ec0F0db8bAF250eCccF268D7dFbF59346E5E", ForkType.UNISWAP_V3),
    AMM("Ramses", "0x07E60782535752be279929e2DFfDd136Db2e6b45", ForkType.UNISWAP_V3),

    # NOTE: ProjectX factory address not confirmed yet:
    # AMM("ProjectX", "0x...", ForkType.UNISWAP_V3),

    # ── Algebra-style (Pool event emitted by factory) ─────────────
    AMM("HyperCat", "0x1d9DcF8238daf2E078FF639a5Ded6b518BF3E585", ForkType.ALGEBRA),
    AMM("Nest", "0x9e41C550D1Ff3913F09b7CfbB9dA17d3dD80dD31", ForkType.ALGEBRA),
    AMM("Liquidity", "0x10253594a832f967994b44f33411940533302acb", ForkType.ALGEBRA),
]

# ── Event topic0 hashes ──────────────────────────────────────────

PAIR_CREATED_V2 = Web3.keccak(text="PairCreated(address,address,address,uint256)").hex()
POOL_CREATED_V3 = Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)").hex()
POOL_ALGEBRA   = Web3.keccak(text="Pool(address,address,address)").hex()
MINT_V2        = Web3.keccak(text="Mint(address,uint256,uint256)").hex()
MINT_V3        = Web3.keccak(text="Mint(address,address,int24,int24,uint128,uint256,uint256)").hex()
INCREASE_LIQ   = Web3.keccak(text="IncreaseLiquidity(uint256,uint128,uint256,uint256)").hex()
SWAP_V2        = Web3.keccak(text="Swap(address,uint256,uint256,uint256,uint256,address)").hex()
SWAP_V3        = Web3.keccak(text="Swap(address,address,int256,int256,uint160,uint128,int24)").hex()

# Minimal ABIs for on-chain reads
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]

PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
]
