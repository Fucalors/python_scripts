import time
from decimal import Decimal, getcontext
from datetime import datetime
from web3 import Web3
import requests
import json
import logging
from eth_abi import encode
from config import (
    BSC_RPC_URLS,  # RPC节点列表
    MIXED_QUOTER_ADDR, CL_POOL_MANAGER_ADDR,
    TRADING_PAIRS, EXCHANGE_FEE_RATE, CHECK_INTERVAL,
    DINGTALK_WEBHOOKS,  # Webhook列表
    GATE_ORDERBOOK_URL,
    MIXED_QUOTER_ABI, CL_POOL_MANAGER_ABI
)
import zoneinfo

beijing_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
getcontext().prec = 50

# 当前使用的RPC索引和Webhook索引
current_rpc_index = 0
current_webhook_index = 0

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 全局变量
web3 = None
current_rpc = None
mixed_quoter_contract = None
cl_pool_manager_contract = None


def init_web3(rpc_url):
    """初始化Web3连接"""
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if w3.is_connected():
        return w3
    return None


def get_next_rpc():
    """获取下一个可用的RPC节点"""
    global current_rpc_index
    rpc_urls = BSC_RPC_URLS.copy()

    for i in range(len(rpc_urls)):
        idx = (current_rpc_index + i) % len(rpc_urls)
        w3 = init_web3(rpc_urls[idx])
        if w3:
            current_rpc_index = (idx + 1) % len(rpc_urls)  # 下次从下一个开始
            return w3, rpc_urls[idx]
    raise ConnectionError("所有BSC RPC节点连接失败！请检查配置")


class MixedQuoter:
    """MixedQuoter合约封装类"""
    def __init__(self, web3_instance, quoter_address, pool_manager_address):
        self.web3 = web3_instance
        self.quoter_contract = web3_instance.eth.contract(
            address=quoter_address,
            abi=MIXED_QUOTER_ABI
        )
        self.pool_manager_contract = web3_instance.eth.contract(
            address=pool_manager_address,
            abi=CL_POOL_MANAGER_ABI
        )
        self.actions = {
            "v3": 0x03,
            "v4": 0x04
        }
    
    def get_pool_key_from_pool_id(self, pool_id):
        """从poolId获取PoolKey"""
        try:
            pool_id_bytes = bytes.fromhex(pool_id.replace("0x", ""))
            pool_key = self.pool_manager_contract.functions.poolIdToPoolKey(pool_id_bytes).call()
            return {
                "currency0": pool_key[0],
                "currency1": pool_key[1],
                "hooks": pool_key[2],
                "poolManager": pool_key[3],
                "fee": pool_key[4],
                "parameters": pool_key[5],
                "hookData": b''
            }
        except Exception as e:
            logging.error(f"Error getting pool key: {e}")
            return None
    
    def encode_cl_pool_params(self, pool_config):
        """编码CL池参数"""
        return encode(
            ["((address,address,address,address,uint24,bytes32),bytes)"],
            [((
                pool_config["currency0"],
                pool_config["currency1"],
                pool_config["hooks"],
                pool_config["poolManager"],
                pool_config["fee"],
                pool_config["parameters"]
            ), pool_config["hookData"])]
        )
    
    def encode_v3_fee(self, fee):
        """编码V3费用参数"""
        return encode(["uint24"], [fee])
    
    def build_paths(self, path_config, tokens):
        """构建交易路径"""
        return [tokens[token]["address"] for token in path_config]
    
    def build_actions(self, actions_config):
        """构建交易动作"""
        return bytes([self.actions[action] for action in actions_config])
    
    def build_params(self, path_config, actions_config, v3_fees, v4_pool_ids):
        """构建交易参数"""
        params = []
        
        for i, (action, token_in, token_out) in enumerate(zip(actions_config, path_config[:-1], path_config[1:])):
            key = f"{token_in}_{token_out}"
            reverse_key = f"{token_out}_{token_in}"
            
            if action == "v3":
                # V3池子，需要fee参数
                fee = v3_fees.get(key, v3_fees.get(reverse_key, 100))  # 默认fee为100
                params.append(self.encode_v3_fee(fee))
            elif action == "v4":
                # V4池子，需要PoolKey参数
                pool_id = v4_pool_ids.get(key, v4_pool_ids.get(reverse_key))
                if not pool_id:
                    logging.error(f"Error: No pool ID found for {key} or {reverse_key}")
                    return None
                
                pool_config = self.get_pool_key_from_pool_id(pool_id)
                if not pool_config:
                    return None
                
                params.append(self.encode_cl_pool_params(pool_config))
        
        return params
    
    def quote_mixed_exact_input(self, paths, actions, params, amount_in):
        """调用quoteMixedExactInput函数"""
        try:
            amount_out, gas_estimate = self.quoter_contract.functions.quoteMixedExactInput(
                paths, actions, params, amount_in
            ).call()
            return amount_out, gas_estimate
        except Exception as e:
            logging.error(f"Error calling quoteMixedExactInput: {e}")
            return None, None


def init_contracts(w3):
    """初始化合约实例"""
    global mixed_quoter_contract, cl_pool_manager_contract
    
    # 初始化MixedQuoter合约
    mixed_quoter_contract = MixedQuoter(
        w3, MIXED_QUOTER_ADDR, CL_POOL_MANAGER_ADDR
    )
    
    # 初始化PoolManager合约
    cl_pool_manager_contract = w3.eth.contract(
        address=CL_POOL_MANAGER_ADDR,
        abi=CL_POOL_MANAGER_ABI
    )


def switch_rpc():
    """切换到下一个RPC节点"""
    global web3, current_rpc
    web3, current_rpc = get_next_rpc()
    init_contracts(web3)
    logging.info(f"已切换到RPC节点: {current_rpc}")


# 初始化第一个可用的Web3连接
try:
    web3, current_rpc = get_next_rpc()
    init_contracts(web3)
except Exception as e:
    logging.error(f"初始化RPC节点失败: {e}")
    exit(1)


# -------------------------- 钉钉Webhook轮询 --------------------------
def get_next_webhook():
    """获取下一个Webhook"""
    global current_webhook_index
    if not DINGTALK_WEBHOOKS:
        return None

    webhook = DINGTALK_WEBHOOKS[current_webhook_index]
    current_webhook_index = (current_webhook_index + 1) % len(DINGTALK_WEBHOOKS)
    return webhook


# -------------------------- 核心工具函数 --------------------------






def query_pancake_exchange_rate(pair_config: dict, from_token: str, to_token: str, amount) -> Decimal:
    """查询PancakeSwap汇率（使用MixedQuoter）"""
    try:
        tokens = pair_config["tokens"]
        swap_path = pair_config["swap_path"]
        actions_config = pair_config["actions"]
        v3_fees = pair_config.get("v3_fees", {})
        v4_pool_ids = pair_config.get("v4_pool_ids", {})

        # 检查路径是否包含from_token和to_token
        if from_token not in swap_path:
            raise ValueError(f"{pair_config['pair_name']} 路径错误：不包含 {from_token}（路径：{swap_path}）")
        if to_token not in swap_path:
            raise ValueError(f"{pair_config['pair_name']} 路径错误：不包含 {to_token}（路径：{swap_path}）")

        # 获取索引
        from_index = swap_path.index(from_token)
        to_index = swap_path.index(to_token)

        # 构建子路径和子动作
        if from_index < to_index:
            # 正向路径
            sub_path = swap_path[from_index:to_index + 1]
            sub_actions = actions_config[from_index:to_index]
        else:
            # 反向路径：需要反转路径和动作
            # 从from_index开始，到to_index结束，步长为-1
            sub_path = swap_path[from_index:to_index-1:-1] if to_index > 0 else swap_path[from_index::-1]
            # 对于actions，需要从to_index开始，到from_index-1结束，然后反转
            sub_actions = actions_config[to_index:from_index][::-1]

        # 检查子路径是否为空
        if not sub_path:
            raise ValueError(
                f"{pair_config['pair_name']} 路径截取错误：from={from_token}（索引{from_index}），to={to_token}（索引{to_index}）"
            )

        # 构建路径
        paths = mixed_quoter_contract.build_paths(sub_path, tokens)
        
        # 构建动作
        actions = mixed_quoter_contract.build_actions(sub_actions)
        
        # 构建参数
        params = mixed_quoter_contract.build_params(
            sub_path,
            sub_actions,
            v3_fees,
            v4_pool_ids
        )
        
        if not params:
            raise ValueError("构建参数失败")
        
        # 转换金额为wei单位
        from_token_info = tokens[from_token]
        amount_wei = int(amount * (10 ** from_token_info["decimals"]))
        if amount_wei <= 0:
            raise ValueError(f"无效输入金额: {amount}")
        
        # 调用MixedQuoter合约
        amount_out_wei, _ = mixed_quoter_contract.quote_mixed_exact_input(
            paths, actions, params, amount_wei
        )
        
        if amount_out_wei is None:
            raise ValueError("调用quoteMixedExactInput失败")
        
        # 转换为实际数量
        to_token_info = tokens[to_token]
        amount_out = Decimal(amount_out_wei) / Decimal(10 ** to_token_info["decimals"])
        return amount_out / Decimal(amount) if amount != 0 else Decimal(0)
        
    except Exception as e:
        logging.info(f"{pair_config['pair_name']} PancakeSwap {from_token}→{to_token} 汇率查询失败: {e}")
        return Decimal(0)


def fetch_gate_orderbook(pair_config: dict) -> dict:
    """获取Gate.io订单簿数据"""
    params = {
        "currency_pair": pair_config["gate_symbol"].upper(),
        "limit": pair_config["orderbook_depth"]
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(GATE_ORDERBOOK_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        bids = [(Decimal(p), Decimal(q)) for p, q in data.get("bids", [])]
        asks = [(Decimal(p), Decimal(q)) for p, q in data.get("asks", [])]

        return {"bids": bids, "asks": asks, "success": True, "depth": pair_config["orderbook_depth"]}
    except Exception as e:
        logging.info(f"{pair_config['pair_name']} Gate.io订单簿请求失败: {str(e)}")
        return {"bids": [], "asks": [], "success": False, "depth": pair_config["orderbook_depth"]}


def simulate_order_execution(amount: Decimal, orders: list, is_buy: bool = True) -> dict:
    """模拟订单按最优价格吃单"""
    remaining_amount = amount
    total_tokens = Decimal(0)
    total_cost = Decimal(0)

    # 检测订单簿深度
    if not orders:
        logging.warning(f"订单簿为空，无法模拟执行订单")
        return {
            "used_amount": Decimal(0),
            "tokens_obtained": Decimal(0),
            "avg_price": Decimal(0),
            "remaining_amount": amount,
            "depth_insufficient": True
        }

    # 排序订单：买入优先低价，卖出优先高价
    processed_orders = sorted(orders, key=lambda x: x[0], reverse=not is_buy)

    for price, quantity in processed_orders:
        if remaining_amount <= 0:
            break

        if is_buy:
            # 买入：用金额计算可买数量
            max_possible_tokens = remaining_amount / price
            if max_possible_tokens <= quantity:
                total_tokens += max_possible_tokens
                total_cost += remaining_amount
                remaining_amount = 0
            else:
                total_tokens += quantity
                total_cost += price * quantity
                remaining_amount -= price * quantity
        else:
            # 卖出：用数量计算可卖金额
            if quantity <= remaining_amount:
                total_tokens += quantity
                total_cost += price * quantity
                remaining_amount -= quantity
            else:
                total_tokens += remaining_amount
                total_cost += price * remaining_amount
                remaining_amount = 0

    # 检测订单簿深度是否足够
    depth_insufficient = False
    if remaining_amount > 0:
        depth_insufficient = True
        action = "买入" if is_buy else "卖出"
        remaining_percentage = (remaining_amount / amount) * 100 if amount > 0 else 0
        logging.warning(f"订单簿深度不足，无法完成{action}操作。剩余{remaining_percentage:.2f}%的订单未执行")

    avg_price = total_cost / total_tokens if total_tokens > 0 else Decimal(0)
    return {
        "used_amount": total_cost,
        "tokens_obtained": total_tokens,
        "avg_price": avg_price,
        "remaining_amount": remaining_amount,
        "depth_insufficient": depth_insufficient
    }


def send_markdown_notification(content: str, title: str):
    """发送钉钉markdown通知（轮询Webhook）"""
    webhook = get_next_webhook()
    if not webhook:
        logging.info("未配置钉钉Webhook，无法发送通知")
        return

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content.strip()
        }
    }
    headers = {"Content-Type": "application/json"}
    logging.info(f"[钉钉通知] 使用Webhook {webhook[-20:]} 发送: {title}")

    try:
        response = requests.post(webhook, headers=headers, data=json.dumps(payload), timeout=5)
        response.raise_for_status()
        return True
    except Exception as ex:
        logging.info(f"钉钉通知发送失败: {ex}，尝试下一个Webhook")
        # 立即尝试下一个Webhook
        webhook = get_next_webhook()
        if webhook:
            try:
                requests.post(webhook, headers=headers, data=json.dumps(payload), timeout=5)
            except Exception as ex2:
                logging.info(f"再次发送失败: {ex2}")
        return False


def calculate_arbitrage_profit(pair_config: dict, path: str, gate_data: dict) -> dict:
    """计算套利利润"""
    result = {"profit": Decimal(0), "rate": Decimal(0)}
    if not gate_data["success"]:
        return result

    input_amount = pair_config["input_amount"]
    bids = gate_data["bids"]
    asks = gate_data["asks"]
    base_name = pair_config["tokens"]["base"]["name"]
    quote_name = pair_config["tokens"]["quote"]["name"]

    if path == "A":
        # 路径A：报价代币（链上）→基础代币（兑换）→报价代币（Gate）
        # 直接使用input_amount查询链上兑换，考虑价格影响
        unit_rate = query_pancake_exchange_rate(pair_config, "quote", "base", input_amount)
        base_bought = unit_rate * input_amount
        
        if base_bought <= 0:
            return result
            
        sell_result = simulate_order_execution(base_bought, bids, is_buy=False)  # 模拟卖出
        
        # 检查订单簿深度是否足够
        if sell_result.get("depth_insufficient", False):
            logging.warning(f"{pair_config['pair_name']} 路径A：订单簿深度不足，无法完成卖出操作")
            return result
            
        quote_sold = sell_result["used_amount"] * (Decimal(1) - EXCHANGE_FEE_RATE)
        # 计算利润
        profit = quote_sold - input_amount
        rate_profit = profit / input_amount if input_amount > 0 else Decimal(0)

        result.update({
            "input": input_amount,
            "base_bought": base_bought,
            "quote_out": quote_sold,
            "profit": profit,
            "rate": rate_profit,
            "avg_sell_price": sell_result["avg_price"],
            "executed_tokens": sell_result["tokens_obtained"],
            "base_name": base_name,
            "quote_name": quote_name
        })

    elif path == "B":
        # 路径B：报价代币→基础代币（Gate）→报价代币（链上兑换）
        available_amount = input_amount * (Decimal(1) - EXCHANGE_FEE_RATE)
        buy_result = simulate_order_execution(available_amount, asks, is_buy=True)  # 模拟买入
        
        # 检查订单簿深度是否足够
        if buy_result.get("depth_insufficient", False):
            logging.warning(f"{pair_config['pair_name']} 路径B：订单簿深度不足，无法完成买入操作")
            return result
            
        base_bought = buy_result["tokens_obtained"]
        
        if base_bought <= 0:
            return result
            
        # 用实际买入的数量查询链上兑换，考虑价格影响
        unit_rate = query_pancake_exchange_rate(pair_config, "base", "quote", float(base_bought))
        quote_received = unit_rate * base_bought
        # 计算利润
        profit = quote_received - input_amount
        rate_profit = profit / input_amount if input_amount > 0 else Decimal(0)

        result.update({
            "input": input_amount,
            "base_bought": base_bought,
            "quote_received": quote_received,
            "profit": profit,
            "rate": rate_profit,
            "avg_buy_price": buy_result["avg_price"],
            "used_amount": buy_result["used_amount"],
            "base_name": base_name,
            "quote_name": quote_name
        })
    return result


# -------------------------- 套利检测主逻辑 --------------------------
def check_arbitrage_for_pair(pair_config: dict):
    """检查单个交易对的套利机会"""
    try:
        pair_name = pair_config["pair_name"]
        logging.info(f"\n🔍 开始检测 {pair_name} 套利机会...")

        # 获取Gate.io订单簿
        gate_data = fetch_gate_orderbook(pair_config)
        if not gate_data["success"]:
            logging.info(f"{pair_name} Gate.io订单簿获取失败，尝试备选格式...")
            original_symbol = pair_config["gate_symbol"]
            pair_config["gate_symbol"] = original_symbol.replace("_", "-")
            gate_data = fetch_gate_orderbook(pair_config)
            pair_config["gate_symbol"] = original_symbol
            if not gate_data["success"]:
                logging.info(f"{pair_name} Gate.io订单簿获取失败，跳过本次检测")
                return

        # 计算路径A利润（链上买→Gate卖）
        path_a_result = calculate_arbitrage_profit(pair_config, "A", gate_data)
        logging.info(
            f"📈 路径A {pair_name} 链上买→Gate卖: "
            f"投入{path_a_result['input']}{path_a_result['quote_name']} → "
            f"获得{path_a_result['base_bought']:.6f}{path_a_result['base_name']} → "
            f"卖出得{path_a_result['quote_out']:.6f}{path_a_result['quote_name']} | "
            f"利润: {path_a_result['profit']:.6f}{path_a_result['quote_name']} | "
            f"利润率: {path_a_result['rate']:.6%}"
        )
        if path_a_result["rate"] >= pair_config["arbitrage_threshold"]:
            base_address = pair_config["tokens"]["base"]["address"]
            remark = pair_config.get("remark", "无")
            notification_title = f"{pair_name} 链上买→Gate卖"
            content = (
                f"### {notification_title} [](info)\n"
                f"- 投入: {path_a_result['input']} {path_a_result['quote_name']}\n"
                f"- 链上兑换: {path_a_result['input']} {path_a_result['quote_name']} → {path_a_result['base_bought']:.6f} {path_a_result['base_name']}\n"
                f"- Gate卖出: {path_a_result['executed_tokens']:.6f} {path_a_result['base_name']} → {path_a_result['quote_out']:.6f} {path_a_result['quote_name']}\n"
                f"- 平均卖价: {path_a_result['avg_sell_price']:.6f}\n"
                f"- 利润: {path_a_result['profit']:.6f} {path_a_result['quote_name']}\n"
                f"- 收益率: {path_a_result['rate']:.2%}\n"
                f"- 行情面板: https://web3.okx.com/zh-hans/token/bsc/{base_address}\n"
                f"- 备注信息: {remark}\n"
                f"- 时间: {datetime.now(beijing_tz):%Y-%m-%d %H:%M:%S}"
            )
            send_markdown_notification(content, notification_title)

        # 计算路径B利润（Gate买→链上卖）
        path_b_result = calculate_arbitrage_profit(pair_config, "B", gate_data)
        logging.info(
            f"📉 路径B {pair_name} Gate买→链上卖: "
            f"投入{path_b_result['input']}{path_b_result['quote_name']} → "
            f"买入{path_b_result['base_bought']:.6f}{path_b_result['base_name']} → "
            f"链上兑换得{path_b_result['quote_received']:.6f}{path_b_result['quote_name']} | "
            f"利润: {path_b_result['profit']:.6f}{path_b_result['quote_name']} | "
            f"利润率: {path_b_result['rate']:.6%}"
        )
        if path_b_result["rate"] >= pair_config["arbitrage_threshold"]:
            base_address = pair_config["tokens"]["base"]["address"]
            remark = pair_config.get("remark", "无")
            notification_title = f"{pair_name} Gate买→链上卖"
            content = (
                f"### {notification_title} [](info)\n"
                f"- 投入: {path_b_result['input']} {path_b_result['quote_name']}\n"
                f"- Gate买入: {path_b_result['input']} {path_b_result['quote_name']} → {path_b_result['base_bought']:.6f} {path_b_result['base_name']}\n"
                f"- 链上兑换: {path_b_result['base_bought']:.6f} {path_b_result['base_name']} → {path_b_result['quote_received']:.6f} {path_b_result['quote_name']}\n"
                f"- 平均买价: {path_b_result['avg_buy_price']:.6f}\n"
                f"- 利润: {path_b_result['profit']:.6f} {path_b_result['quote_name']}\n"
                f"- 收益率: {path_b_result['rate']:.2%}\n"
                f"- 行情面板: https://web3.okx.com/zh-hans/token/bsc/{base_address}\n"
                f"- 备注信息: {remark}\n"
                f"- 时间: {datetime.now(beijing_tz):%Y-%m-%d %H:%M:%S}"
            )
            send_markdown_notification(content, notification_title)

    except Exception as e:
        logging.info(f"{pair_config['pair_name']} 套利检测异常: {e}")


def check_all_pairs():
    """检查所有交易对"""
    for pair in TRADING_PAIRS:
        if pair["enabled"]:
            check_arbitrage_for_pair(pair)


# -------------------------- 启动通知 --------------------------
def send_start_notification():
    """发送启动通知"""
    enabled_pairs = [p["pair_name"] for p in TRADING_PAIRS if p["enabled"]]
    content = (
        f"### PancakeSwap-Gate.io套利监控启动[](info)\n"
        f"- 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 监控交易对: {', '.join(enabled_pairs) or '无'}\n"
        f"- 检测间隔: {CHECK_INTERVAL}秒\n"
        f"- 支持版本: PancakeSwap MixedQuoter (V3 & V4)\n"
    )
    send_markdown_notification(content, "PancakeSwap-Gate.io套利监控")


# -------------------------- 主循环 --------------------------
if __name__ == "__main__":
    send_start_notification()
    while True:
        try:
            logging.info(f"\n🕒 {datetime.now():%Y-%m-%d %H:%M:%S} 开始交易对检测...")
            logging.info(f"当前使用RPC节点: {current_rpc}")
            check_all_pairs()
            # 每次检测完成后切换到下一个RPC节点
            switch_rpc()
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logging.info(f"主循环异常: {e}，尝试切换RPC节点并继续...")
            switch_rpc()
            time.sleep(5)  # 异常重试