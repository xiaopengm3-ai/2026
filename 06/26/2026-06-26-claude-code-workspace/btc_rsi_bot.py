"""
BTC RSI 自动交易机器人 — 基于 ccxt
策略：无持仓时，RSI 超卖做多 / 超买做空
"""
import time
import numpy as np
from datetime import datetime
import ccxt

# ===== 配置 =====
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"
RSI_PERIOD = 14
RSI_OVERSOLD = 30      # RSI 低于此值开多
RSI_OVERBOUGHT = 70    # RSI 高于此值开空
SLEEP_SECONDS = 60
RETRY_SECONDS = 30


def calc_rsi(closes, period=14):
    """计算 RSI"""
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def fetch_position(exchange):
    """获取当前持仓"""
    try:
        positions = exchange.fetch_positions([SYMBOL])
        for p in positions:
            if float(p.get("contracts", 0)) > 0:
                return p
        return None
    except Exception:
        return None


def calc_order_params(exchange, side, last_price):
    """计算开仓参数（保证金、数量）"""
    # 用账户余额的 10% 作为保证金
    balance = exchange.fetch_balance()
    usdt = balance["USDT"]["free"]
    margin = usdt * 0.1
    amount = margin / last_price
    return {"side": side, "amount": amount, "margin": margin}


def place_order(exchange, params):
    """下单"""
    order = exchange.create_order(
        symbol=SYMBOL,
        type="market",
        side=params["side"],
        amount=params["amount"],
    )
    return order


def main():
    exchange = ccxt.binance({
        "apiKey": "YOUR_API_KEY",
        "secret": "YOUR_SECRET",
        "options": {"defaultType": "future"},
    })
    exchange.set_sandbox_mode(True)  # 先跑模拟盘

    print(f"[启动] {SYMBOL} RSI 策略 | 时间框架: {TIMEFRAME} | RSI周期: {RSI_PERIOD}")
    print(f"[启动] 超卖阈值: {RSI_OVERSOLD} | 超买阈值: {RSI_OVERBOUGHT}")

    while True:
        try:
            # 获取持仓
            position = fetch_position(exchange)

            # 获取行情
            ticker = exchange.fetch_ticker(SYMBOL)
            last_price = ticker["last"]

            # 获取 K 线并计算 RSI
            ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=RSI_PERIOD + 50)
            closes = np.array([candle[4] for candle in ohlcv], dtype=float)
            rsi = calc_rsi(closes, RSI_PERIOD)

            # 打印状态
            now = datetime.now().strftime("%H:%M:%S")
            if position:
                pos_side = "多" if position["side"] == "long" else "空"
                pos_pnl = round(float(position.get("unrealizedPnl", 0)), 2)
                pos_str = f"{pos_side} {position['contracts']}张 | 浮动盈亏: {pos_pnl}"
            else:
                pos_str = "无持仓"

            rsi_str = f"{rsi:.1f}" if rsi is not None else "计算中..."
            print(f"[{now}] BTC {last_price:.1f} | RSI({RSI_PERIOD})={rsi_str} | {pos_str}")

            # 开仓信号（无持仓时）
            if position is None and rsi is not None:
                if rsi < RSI_OVERSOLD:
                    params = calc_order_params(exchange, "buy", last_price)
                    if params["margin"] >= 0.5:  # 最低 0.5 USDT
                        print(f"\n[信号] RSI {rsi:.1f} < {RSI_OVERSOLD} → 触发开多")
                        place_order(exchange, params)
                    else:
                        print(f"  [SKIP] 保证金不足 ({params['margin']:.2f} USDT)")

                elif rsi > RSI_OVERBOUGHT:
                    params = calc_order_params(exchange, "sell", last_price)
                    if params["margin"] >= 0.5:
                        print(f"\n[信号] RSI {rsi:.1f} > {RSI_OVERBOUGHT} → 触发开空")
                        place_order(exchange, params)
                    else:
                        print(f"  [SKIP] 保证金不足 ({params['margin']:.2f} USDT)")

            time.sleep(SLEEP_SECONDS)

        except KeyboardInterrupt:
            print("\n[INFO] 用户终止")
            break
        except ccxt.NetworkError as e:
            print(f"[WARN] 网络错误: {e}")
            time.sleep(RETRY_SECONDS)
        except ccxt.ExchangeError as e:
            print(f"[WARN] 交易所错误: {e}")
            time.sleep(RETRY_SECONDS)
        except Exception as e:
            print(f"[ERROR] 未知错误: {e}")
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
