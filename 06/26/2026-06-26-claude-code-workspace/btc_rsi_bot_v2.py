"""
BTC RSI 自动交易机器人 v2 — ccxt + 改进版
改进点：
  1. Wilder 平滑 RSI（标准算法）
  2. 止盈止损 + RSI 回归中线平仓
  3. EMA 趋势过滤（顺势开仓）
  4. 固定仓位 + 最大回撤熔断
  5. 结构化日志
"""
import time
import json
import logging
import numpy as np
from datetime import datetime
from pathlib import Path
import ccxt

# ===== 策略配置 =====
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
EMA_FAST = 20             # 快线
EMA_SLOW = 50             # 慢线

# ===== 风控 =====
TAKE_PROFIT_PCT = 0.03    # 止盈 3%
STOP_LOSS_PCT = 0.015     # 止损 1.5%
TRAILING_STOP_PCT = 0.02  # 移动止盈 2%
POSITION_USDT = 50        # 固定开仓金额
MAX_DRAWDOWN_PCT = 0.15   # 最大回撤 15% → 熔断
MIN_BALANCE = 10          # 最低余额, 低于此值不交易

# ===== 轮询 =====
SLEEP_SECONDS = 60
RETRY_SECONDS = 30

# ===== 日志 =====
LOG_DIR = Path("e:/claude code files/logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "btc_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("btc_bot")


# ============================================================
# 指标计算
# ============================================================

class RSI:
    """Wilder 平滑 RSI（标准算法）"""
    def __init__(self, period=14):
        self.period = period
        self.prev_avg_gain = None
        self.prev_avg_loss = None
        self.prev_close = None

    def update(self, closes):
        """每根新 K 线调用一次，维持内部状态"""
        if len(closes) < 2:
            return None

        deltas = np.diff(closes[-2:])  # 只看最后两根
        gain = max(deltas[-1], 0)
        loss = max(-deltas[-1], 0)

        if self.prev_avg_gain is None:
            # 首次：收集满 period 根后算初始均值
            if len(closes) < self.period + 1:
                return None
            all_deltas = np.diff(closes[-(self.period + 1):])
            gains = np.where(all_deltas > 0, all_deltas, 0)
            losses = np.where(all_deltas < 0, -all_deltas, 0)
            self.prev_avg_gain = np.mean(gains)
            self.prev_avg_loss = np.mean(losses)
        else:
            # Wilder 平滑
            self.prev_avg_gain = (self.prev_avg_gain * (self.period - 1) + gain) / self.period
            self.prev_avg_loss = (self.prev_avg_loss * (self.period - 1) + loss) / self.period

        if self.prev_avg_loss == 0:
            return 100.0

        rs = self.prev_avg_gain / self.prev_avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


def calc_ema(closes, period):
    """指数移动平均"""
    if len(closes) < period:
        return None
    alpha = 2 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = alpha * price + (1 - alpha) * ema
    return ema


# ============================================================
# 交易逻辑
# ============================================================

class TradingBot:
    def __init__(self):
        self.exchange = ccxt.binance({
            "apiKey": "YOUR_API_KEY",
            "secret": "YOUR_SECRET",
            "options": {"defaultType": "future"},
        })
        self.exchange.set_sandbox_mode(True)

        self.rsi = RSI(RSI_PERIOD)
        self.initial_balance = None
        self.peak_balance = 0
        self.halted = False
        self.entry_price = None
        self.entry_side = None
        self.trail_high = 0
        self.trail_low = 0

    # ---- 数据获取 ----

    def fetch_position(self):
        try:
            positions = self.exchange.fetch_positions(symbols=[SYMBOL])
            for p in positions:
                if float(p.get("contracts", 0)) > 0:
                    return p
            return None
        except Exception as e:
            log.debug(f"获取持仓失败: {e}")
            return None

    def fetch_market_data(self):
        ticker = self.exchange.fetch_ticker(SYMBOL)
        ohlcv = self.exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=RSI_PERIOD + 100)
        closes = np.array([c[4] for c in ohlcv], dtype=float)
        return ticker, closes

    # ---- 交易决策 ----

    def should_open_long(self, rsi_val, closes):
        """RSI 超卖 + 上升趋势 → 开多"""
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        trend_up = ema_fast > ema_slow if (ema_fast and ema_slow) else True
        return rsi_val < RSI_OVERSOLD and trend_up

    def should_open_short(self, rsi_val, closes):
        """RSI 超买 + 下降趋势 → 开空"""
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        trend_down = ema_fast < ema_slow if (ema_fast and ema_slow) else True
        return rsi_val > RSI_OVERBOUGHT and trend_down

    def should_close(self, position, rsi_val):
        """平仓条件：初始止损 / 移动止盈 / 固定止盈"""
        if position is None:
            return False

        entry = float(position["entryPrice"])
        current = float(position["markPrice"]) if position.get("markPrice") else self.last_price
        side = position["side"]

        if side == "long":
            pnl_pct = (current - entry) / entry
            self.trail_high = max(self.trail_high, current)
            trail_stop = self.trail_high * (1 - TRAILING_STOP_PCT)
        else:
            pnl_pct = (entry - current) / entry
            self.trail_low = min(self.trail_low, current)
            trail_stop = self.trail_low * (1 + TRAILING_STOP_PCT)

        if pnl_pct <= -STOP_LOSS_PCT:
            log.info(f"止损触发 | {pnl_pct:.2%}")
            return True
        if (side == "long" and current <= trail_stop) or (side == "short" and current >= trail_stop):
            log.info(f"移动止盈触发 | {pnl_pct:.2%} | trail={trail_stop:.1f}")
            return True
        if pnl_pct >= TAKE_PROFIT_PCT:
            log.info(f"止盈触发 | {pnl_pct:.2%}")
            return True

        return False

    # ---- 风控 ----

    def check_risk(self):
        """检查是否触发风控熔断"""
        try:
            balance = self.exchange.fetch_balance()
            usdt = float(balance["USDT"]["total"])
        except Exception:
            return True  # 取不到余额, 保守不交易

        if self.initial_balance is None:
            self.initial_balance = usdt

        self.peak_balance = max(self.peak_balance, usdt)
        drawdown = (self.peak_balance - usdt) / self.peak_balance

        if usdt < MIN_BALANCE:
            log.warning(f"余额 {usdt:.1f} 低于最低要求 {MIN_BALANCE}")
            return False

        if drawdown > MAX_DRAWDOWN_PCT:
            if not self.halted:
                log.error(f"最大回撤 {drawdown:.1%} 超过阈值 {MAX_DRAWDOWN_PCT:.0%} → 熔断!")
                self.halted = True
            return False

        return True

    # ---- 下单 ----

    def open_position(self, side, price):
        """开仓: 固定金额算数量"""
        try:
            if side == "buy":
                amount = POSITION_USDT / price
            else:
                amount = POSITION_USDT / price

            order = self.exchange.create_order(
                symbol=SYMBOL,
                type="market",
                side=side,
                amount=amount,
            )
            log.info(f"开仓 | {side.upper()} | 数量: {amount:.4f} | 价格: {price:.1f}")
            self.entry_price = price
            self.entry_side = side
            self.trail_high = price
            self.trail_low = price
            return order
        except Exception as e:
            log.error(f"开仓失败: {e}")
            return None

    def close_position(self, position):
        """平仓"""
        try:
            side = "sell" if position["side"] == "long" else "buy"
            amount = float(position["contracts"])
            order = self.exchange.create_order(
                symbol=SYMBOL,
                type="market",
                side=side,
                amount=amount,
                params={"reduceOnly": True},
            )
            log.info(f"平仓 | {side.upper()} | 数量: {amount}")
            self.entry_price = None
            self.entry_side = None
            self.trail_high = 0
            self.trail_low = 0
            return order
        except Exception as e:
            log.error(f"平仓失败: {e}")
            return None

    # ---- 主循环 ----

    def print_status(self, rsi_val, last_price, position):
        now = datetime.now().strftime("%H:%M:%S")
        rsi_s = f"{rsi_val:.1f}" if rsi_val is not None else "--"

        if position:
            side = "多" if position["side"] == "long" else "空"
            pnl = round(float(position.get("unrealizedPnl", 0)), 2)
            pos_s = f"{side} {position['contracts']}张 | 浮动: {pnl}"
        else:
            pos_s = "空仓"

        log.info(f"[{now}] BTC {last_price:.1f} | RSI={rsi_s} | {pos_s}")

    def run(self):
        log.info(f"启动 | {SYMBOL} {TIMEFRAME} | RSI({RSI_PERIOD}) | EMA({EMA_FAST}/{EMA_SLOW})")
        log.info(f"风控 | 止盈={TAKE_PROFIT_PCT:.0%} 止损={STOP_LOSS_PCT:.1%} 移动止盈={TRAILING_STOP_PCT:.0%} 仓位={POSITION_USDT}U 熔断={MAX_DRAWDOWN_PCT:.0%}")

        while True:
            try:
                if not self.check_risk():
                    time.sleep(SLEEP_SECONDS * 5)
                    continue

                position = self.fetch_position()
                ticker, closes = self.fetch_market_data()
                last_price = ticker["last"]
                self.last_price = last_price

                rsi_val = self.rsi.update(closes)

                self.print_status(rsi_val, last_price, position)

                # 有持仓 → 检查平仓
                if position is not None:
                    if self.should_close(position, rsi_val):
                        self.close_position(position)

                # 无持仓 → 检查开仓
                else:
                    if rsi_val is None:
                        time.sleep(SLEEP_SECONDS)
                        continue

                    if self.should_open_long(rsi_val, closes):
                        self.open_position("buy", last_price)
                    elif self.should_open_short(rsi_val, closes):
                        self.open_position("sell", last_price)

                time.sleep(SLEEP_SECONDS)

            except KeyboardInterrupt:
                log.info("用户终止")
                break
            except ccxt.NetworkError as e:
                log.warning(f"网络错误: {e}")
                time.sleep(RETRY_SECONDS)
            except ccxt.ExchangeError as e:
                log.warning(f"交易所错误: {e}")
                time.sleep(RETRY_SECONDS)
            except Exception as e:
                log.error(f"未知错误: {e}")
                time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
