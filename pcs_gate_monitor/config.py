from decimal import Decimal
from web3 import Web3

BSC_RPC_URLS = ["https://bscrpc.pancakeswap.finance",
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-mainnet.public.blastapi.io",
    "https://bsc.drpc.org",
    "https://bsc-rpc.publicnode.com",
    "https://bsc-dataseed.nariox.org",
    "https://bsc-dataseed.defibit.io",
    "https://bsc-dataseed.ninicoin.io",
    "https://bsc.nodereal.io",
    "https://bsc-dataseed-public.bnbchain.org",
    "https://wallet.okex.org/fullnode/bsc/discover/rpc",
]
DINGTALK_WEBHOOKS =[
"https://oapi.dingtalk.com/robot/send?access_token=4ff925004d5b99c615867519e85c398c6a052890fb6d35c9a9e80513f797b326",  # 小北监控群
"https://oapi.dingtalk.com/robot/send?access_token=8ce3022b859f85792009ffe4a2d762fd0511933b9845a997ece8d9169f137e23",
"https://oapi.dingtalk.com/robot/send?access_token=1e4aef7e3c173753c52ac54ec811f1271a455271b2fbab877ecb88d48bf68368"
]  # 钉钉通知Webhook
MIXED_QUOTER_ADDR = Web3.to_checksum_address("0x2dCbF7B985c8C5C931818e4E107bAe8aaC8dAB7C")  # PancakeSwap MixedQuoter地址
CL_POOL_MANAGER_ADDR = Web3.to_checksum_address("0xa0FfB9c1CE1Fe56963B0321B32E7A0302114058b")  # PancakeSwap CLPoolManager地址 (V4)
EXCHANGE_FEE_RATE = Decimal('0.001')  # 交易所手续费率（0.1%）
CHECK_INTERVAL = 30  # 套利检测间隔时间（秒）

GATE_ORDERBOOK_URL = "https://api.gateio.ws/api/v4/spot/order_book"  # Gate.io订单簿API地址

TRADING_PAIRS = [
    # 交易对示例 - 混合V3和V4
    {
        "pair_name": "UAI/USDT",
        "gate_symbol": "UAI_USDT",
        "orderbook_depth": 20,
        "input_amount": Decimal(1000),
        "arbitrage_threshold": Decimal("0.005"),
        "remark": "UAI代币",
        "enabled": True,
        "tokens": {
            "base": {
                "name": "UAI",
                "address": Web3.to_checksum_address("0x3E5d4f8aee0D9B3082d5f6DA5D6e225D17ba9ea0"),
                "decimals": 18
            },
            "quote": {
                "name": "USDT",
                "address": Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955"),
                "decimals": 18
            },
            "middle": {
                "name": "WBNB",
                "address": Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
                "decimals": 18
            }
        },
        "swap_path": ["quote", "middle", "base"],
        "actions": ["v3", "v4"],
        "v3_fees": {
            "quote_middle": 100
        },
        "v4_pool_ids": {
            "middle_base": "0x57004a34731b96d9e86b706cd629f24456ca2c7bdfcc5aae2417496d65090eb7"
        }
    },
    {
        "pair_name": "CYS/USDT",
        "gate_symbol": "CYS_USDT",
        "orderbook_depth": 20,
        "input_amount": Decimal(500),
        "arbitrage_threshold": Decimal("0.005"),
        "remark": "CYS代币",
        "enabled": True,
        "tokens": {
            "base": {
                "name": "CYS",
                "address": Web3.to_checksum_address("0x0C69199C1562233640e0Db5Ce2c399A88eB507C7"),
                "decimals": 18
            },
            "quote": {
                "name": "USDT",
                "address": Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955"),
                "decimals": 18
            },
            "middle": {
                "name": "USDC",
                "address": Web3.to_checksum_address("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"),
                "decimals": 18
            }
        },
        "swap_path": ["quote", "middle", "base"],
        "actions": ["v3", "v4"],
        "v3_fees": {
            "quote_middle": 100
        },
        "v4_pool_ids": {
            "middle_base": "0x9cfea9ef82f26857c3426487774c088330555da6113c61ac7fb8b30d0ae434b3"
        }
    },
    # 交易对示例 - 单V4
    {
        "pair_name": "LAB/USDT",
        "gate_symbol": "LAB_USDT",
        "orderbook_depth": 20,
        "input_amount": Decimal(1000),
        "arbitrage_threshold": Decimal("0.005"),
        "remark": "LAB代币",
        "enabled": True,
        "tokens": {
            "base": {
                "name": "LAB",
                "address": Web3.to_checksum_address("0x7ec43cf65f1663f820427c62a5780b8f2e25593a"),
                "decimals": 18
            },
            "quote": {
                "name": "USDT",
                "address": Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955"),
                "decimals": 18
            }
        },
        "swap_path": ["quote", "base"],
        "actions": ["v4"],
        "v4_pool_ids": {
            "quote_base": "0xd9434e63fe78a6e77dafe2abc504121bf8500822f6d3a59eccba577cf0a070f2"
        }
    },
    # 交易对示例 - 单V3
    {
        "pair_name": "KAVA/USDT",
        "gate_symbol": "KAVA_USDT",
        "orderbook_depth": 20,
        "input_amount": Decimal(500),
        "arbitrage_threshold": Decimal("0.01"),
        "remark": "Kava代币",
        "enabled": True,
        "tokens": {
            "base": {
                "name": "KAVA",
                "address": Web3.to_checksum_address("0x9bafc8d4b487cebff201721702507a3e2c67ad79"),
                "decimals": 18
            },
            "quote": {
                "name": "USDT",
                "address": Web3.to_checksum_address("0x55d398326f99059ff775485246999027b3197955"),
                "decimals": 18
            }
        },
        "swap_path": ["quote", "base"],
        "actions": ["v3"],
        "v3_fees": {
            "quote_base": 500
        }
    },
    # 交易对示例 - 多步V3
    {
        "pair_name": "ELIZAOS/USDT",
        "gate_symbol": "ELIZAOS_USDT",
        "orderbook_depth": 30,
        "input_amount": Decimal(1000),
        "arbitrage_threshold": Decimal("0.01"),
        "remark": "ELIZAOS代币",
        "enabled": True,
        "tokens": {
            "base": {
                "name": "ELIZAOS",
                "address": Web3.to_checksum_address("0xea17df5cf6d172224892b5477a16acb111182478"),
                "decimals": 9
            },
            "quote": {
                "name": "USDT",
                "address": Web3.to_checksum_address("0x55d398326f99059ff775485246999027b3197955"),
                "decimals": 18
            },
            "middle": {
                "name": "USDC",
                "address": Web3.to_checksum_address("0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"),
                "decimals": 18
            }
        },
        "swap_path": ["quote", "middle", "base"],
        "actions": ["v3", "v3"],
        "v3_fees": {
            "quote_middle": 100,
            "middle_base": 2500
        }
    }
]


# MixedQuoter合约ABI
MIXED_QUOTER_ABI = [{
 "inputs":[
  {"internalType":"address[]","name":"paths","type":"address[]"},
  {"internalType":"bytes","name":"actions","type":"bytes"},
  {"internalType":"bytes[]","name":"params","type":"bytes[]"},
  {"internalType":"uint256","name":"amountIn","type":"uint256"}
 ],
 "name":"quoteMixedExactInput",
 "outputs":[
  {"internalType":"uint256","name":"amountOut","type":"uint256"},
  {"internalType":"uint256","name":"gasEstimate","type":"uint256"}
 ],
 "stateMutability":"nonpayable",
 "type":"function"
}]

# V4 PoolManager合约ABI
CL_POOL_MANAGER_ABI = [{
    "inputs": [{"internalType": "PoolId", "name": "id", "type": "bytes32"}],
    "name": "poolIdToPoolKey",
    "outputs": [
        {"internalType": "Currency", "name": "currency0", "type": "address"},
        {"internalType": "Currency", "name": "currency1", "type": "address"},
        {"internalType": "contract IHooks", "name": "hooks", "type": "address"},
        {"internalType": "contract IPoolManager", "name": "poolManager", "type": "address"},
        {"internalType": "uint24", "name": "fee", "type": "uint24"},
        {"internalType": "bytes32", "name": "parameters", "type": "bytes32"}
    ],
    "stateMutability": "view", "type": "function"
}]