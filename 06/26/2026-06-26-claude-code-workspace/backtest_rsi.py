"""
BTC RSI 策略回测 — 基于 btc_rsi_bot_v2.py 策略逻辑
"""
import time
import numpy as np
from datetime import datetime, timedelta, timezone
import ccxt
import json

# ===== 策略参数 (与 v2 一致) =====
API_PROXY = "http://127.0.0.1:10809"
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
EMA_FAST = 20
EMA_SLOW = 50
TAKE_PROFIT_PCT = 0.03
STOP_LOSS_PCT = 0.015
TRAILING_STOP_PCT = 0.02   # 移动止盈 2%
POSITION_USDT = 50
MAX_DRAWDOWN_PCT = 0.15

# 回测参数
FETCH_DAYS = 365         # 回测天数 (Binance 单次最多约 1500 根 15m K 线 ≈ 15 天，分批拉)
TAKER_FEE = 0.0006       # Binance futures taker fee 0.06%
SLIPPAGE = 0.0002        # 0.02% 滑点


class RSI:
    """Wilder 平滑 RSI（与 v2 完全一致）"""
    def __init__(self, period=14):
        self.period = period
        self.prev_avg_gain = None
        self.prev_avg_loss = None

    def update(self, closes_slice):
        """closes_slice: 截止当前的所有收盘价"""
        if len(closes_slice) < 2:
            return None

        deltas = np.diff(closes_slice[-2:])
        gain = max(deltas[-1], 0)
        loss = max(-deltas[-1], 0)

        if self.prev_avg_gain is None:
            if len(closes_slice) < self.period + 1:
                return None
            all_deltas = np.diff(closes_slice[-(self.period + 1):])
            gains = np.where(all_deltas > 0, all_deltas, 0)
            losses = np.where(all_deltas < 0, -all_deltas, 0)
            self.prev_avg_gain = np.mean(gains)
            self.prev_avg_loss = np.mean(losses)
        else:
            self.prev_avg_gain = (self.prev_avg_gain * (self.period - 1) + gain) / self.period
            self.prev_avg_loss = (self.prev_avg_loss * (self.period - 1) + loss) / self.period

        if self.prev_avg_loss == 0:
            return 100.0
        rs = self.prev_avg_gain / self.prev_avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


def calc_ema(series, period):
    if len(series) < period:
        return None
    alpha = 2 / (period + 1)
    ema = series[0]
    for val in series[1:]:
        ema = alpha * val + (1 - alpha) * ema
    return ema


def fetch_all_data(exchange, symbol, timeframe, days):
    """分批拉取历史数据"""
    now = datetime.now()
    since_ms = int((now - timedelta(days=days)).timestamp() * 1000)
    all_candles = []

    while True:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=300)
        except Exception as e:
            print(f"  拉取出错: {e}, 等待重试...")
            time.sleep(5)
            continue

        if not candles:
            break

        all_candles.extend(candles)
        print(f"  已拉取 {len(all_candles)} 根 K 线... (最新: {datetime.fromtimestamp(candles[-1][0]/1000).strftime('%m-%d %H:%M')})")
        since_ms = candles[-1][0] + 1

        if len(candles) < 300:
            break
        time.sleep(0.25)

    if not all_candles:
        return np.array([]), []

    # 去重排序
    seen = set()
    unique = []
    for c in sorted(all_candles, key=lambda x: x[0]):
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)
    return np.array([c[4] for c in unique], dtype=float), unique


class Backtest:
    def __init__(self, closes, candles):
        self.closes = closes
        self.candles = candles
        self.rsi = RSI(RSI_PERIOD)

        self.position = None       # "long" or "short"
        self.entry_price = 0
        self.entry_idx = 0
        self.trail_high = 0        # 移动止盈参考价
        self.trail_low = 0
        self.balance = 500         # 初始 500 USDT
        self.initial_balance = 500
        self.peak_balance = 500
        self.halted = False
        self.halted_at = None

        self.trades = []
        self.equity_curve = []

        self.total_fees = 0

    def calc_rsi_at(self, idx):
        return self.rsi.update(self.closes[:idx + 1])

    def ema_trend_up(self, idx):
        """快线 > 慢线 → 上升趋势"""
        if idx < EMA_SLOW:
            return None
        ema_fast = calc_ema(self.closes[:idx + 1], EMA_FAST)
        ema_slow = calc_ema(self.closes[:idx + 1], EMA_SLOW)
        return ema_fast > ema_slow

    def ema_trend_down(self, idx):
        if idx < EMA_SLOW:
            return None
        ema_fast = calc_ema(self.closes[:idx + 1], EMA_FAST)
        ema_slow = calc_ema(self.closes[:idx + 1], EMA_SLOW)
        return ema_fast < ema_slow

    def run(self):
        min_idx = RSI_PERIOD + EMA_SLOW + 2

        for i in range(min_idx, len(self.closes)):
            price = self.closes[i]

            # 熔断检查
            drawdown = (self.peak_balance - self.balance) / self.peak_balance
            if drawdown > MAX_DRAWDOWN_PCT and not self.halted:
                self.halted = True
                self.halted_at = i
                self._close_if_open(price, i, "熔断")

            if self.halted:
                self.equity_curve.append(self.balance)
                continue

            rsi_val = self.calc_rsi_at(i)
            if rsi_val is None:
                self.equity_curve.append(self.balance)
                continue

            if self.position is not None:
                pnl_pct = self._current_pnl(price)
                should_close = False
                reason = ""

                # 更新移动止盈参考价
                if self.position == "long" and price > self.trail_high:
                    self.trail_high = price
                elif self.position == "short" and price < self.trail_low:
                    self.trail_low = price

                # 初始止损
                if pnl_pct <= -STOP_LOSS_PCT:
                    should_close = True
                    reason = "止损"
                # 移动止盈
                elif self.position == "long" and price <= self.trail_high * (1 - TRAILING_STOP_PCT):
                    should_close = True
                    reason = "移动止盈"
                elif self.position == "short" and price >= self.trail_low * (1 + TRAILING_STOP_PCT):
                    should_close = True
                    reason = "移动止盈"
                # 固定止盈
                elif pnl_pct >= TAKE_PROFIT_PCT:
                    should_close = True
                    reason = "止盈"

                if should_close:
                    self._close_position(price, i, reason)
            else:
                trend_up = self.ema_trend_up(i)
                trend_down = self.ema_trend_down(i)

                if rsi_val < RSI_OVERSOLD and trend_up:
                    self._open_position("long", price, i)
                elif rsi_val > RSI_OVERBOUGHT and trend_down:
                    self._open_position("short", price, i)

            self.equity_curve.append(self.balance)

        # 强平最后持仓
        if self.position is not None:
            self._close_position(self.closes[-1], len(self.closes) - 1, "回测结束")

    def _open_position(self, side, price, idx):
        trade_value = POSITION_USDT
        fee = trade_value * TAKER_FEE
        self.total_fees += fee

        # 滑点：开仓时不利方向
        if side == "long":
            exec_price = price * (1 + SLIPPAGE)
        else:
            exec_price = price * (1 - SLIPPAGE)

        self.position = side
        self.entry_price = exec_price
        self.entry_idx = idx
        self.trail_high = exec_price
        self.trail_low = exec_price
        self.balance -= fee  # 开仓手续费先扣

    def _close_position(self, price, idx, reason):
        # 滑点：平仓时不利方向
        if self.position == "long":
            exec_price = price * (1 - SLIPPAGE)
            pnl_pct = (exec_price - self.entry_price) / self.entry_price
        else:
            exec_price = price * (1 + SLIPPAGE)
            pnl_pct = (self.entry_price - exec_price) / self.entry_price

        trade_value = POSITION_USDT
        pnl = trade_value * pnl_pct
        fee = trade_value * TAKER_FEE  # 平仓手续费
        self.total_fees += fee

        self.balance += pnl - fee
        self.peak_balance = max(self.peak_balance, self.balance)

        ts = datetime.fromtimestamp(self.candles[idx][0] / 1000).strftime("%m-%d %H:%M")
        self.trades.append({
            "ts": ts,
            "side": self.position,
            "entry": round(self.entry_price, 1),
            "exit": round(exec_price, 1),
            "pnl_pct": round(pnl_pct * 100, 2),
            "pnl_usdt": round(pnl, 2),
            "reason": reason,
            "bars": idx - self.entry_idx,
            "balance": round(self.balance, 2),
        })

        self.position = None
        self.entry_price = 0
        self.trail_high = 0
        self.trail_low = 0

    def _close_if_open(self, price, idx, reason):
        if self.position is not None:
            self._close_position(price, idx, reason)

    def _current_pnl(self, price):
        if self.position == "long":
            return (price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - price) / self.entry_price

    def report(self):
        if not self.trades:
            print("\n无交易记录")
            return

        wins = [t for t in self.trades if t["pnl_usdt"] > 0]
        losses = [t for t in self.trades if t["pnl_usdt"] <= 0]
        longs = [t for t in self.trades if t["side"] == "long"]
        shorts = [t for t in self.trades if t["side"] == "short"]

        avg_win = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
        avg_loss = np.mean([t["pnl_pct"] for t in losses]) if losses else 0
        total_pnl = sum(t["pnl_usdt"] for t in self.trades)
        total_pnl_pct = round((self.balance - self.initial_balance) / self.initial_balance * 100, 2)

        # 最大回撤
        peak = self.initial_balance
        max_dd = 0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            dd = (peak - eq) / peak
            max_dd = max(max_dd, dd)

        print("\n" + "=" * 60)
        print("  BTC RSI 策略回测报告")
        print("=" * 60)
        print(f"  回测周期: {self.trades[0]['ts']} ~ {self.trades[-1]['ts']}")
        print(f"  数据根数: {len(self.closes)} 根 {TIMEFRAME} K 线")
        print()
        print(f"  初始资金: {self.initial_balance:.1f} USDT")
        print(f"  最终资金: {self.balance:.2f} USDT")
        print(f"  总收益率: {total_pnl_pct}%")
        print(f"  总手续费: {self.total_fees:.2f} USDT")
        print()
        print(f"  总交易数: {len(self.trades)}")
        print(f"   做多: {len(longs)} 笔  做空: {len(shorts)} 笔")
        print(f"   盈利: {len(wins)} 笔 ({len(wins)/len(self.trades)*100:.1f}%)")
        print(f"   亏损: {len(losses)} 笔 ({len(losses)/len(self.trades)*100:.1f}%)")
        print(f"  平均盈利: {avg_win:+.2f}%  平均亏损: {avg_loss:+.2f}%")
        if avg_loss != 0:
            print(f"  盈亏比: {abs(avg_win/avg_loss):.2f}")
        print(f"  最大回撤: {max_dd*100:.2f}%")
        if self.halted:
            print(f"  ⚠ 熔断触发于 {datetime.fromtimestamp(self.candles[self.halted_at][0]/1000).strftime('%m-%d %H:%M')}")
        print()

        # 平仓原因分布
        reasons = {}
        for t in self.trades:
            reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
        print("  平仓原因分布:")
        for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"    {r}: {c} 笔")

        # 交易明细 (最近 30 笔)
        print(f"\n  最近交易明细 (共 {len(self.trades)} 笔, 显示最近 30):")
        print(f"  {'时间':<12} {'方向':<6} {'入场':>10} {'出场':>10} {'盈亏%':>8} {'盈亏U':>8} {'原因':<8} {'持仓K线':>6}")
        print("  " + "-" * 78)
        for t in self.trades[-30:]:
            side = "多" if t["side"] == "long" else "空"
            print(f"  {t['ts']:<12} {side:<6} {t['entry']:>10.1f} {t['exit']:>10.1f} {t['pnl_pct']:>+7.2f}% {t['pnl_usdt']:>+8.2f} {t['reason']:<8} {t['bars']:>4}")

        # 权益曲线摘要
        print(f"\n  权益曲线: {self.initial_balance:.1f} → {self.balance:.2f} (峰值 {self.peak_balance:.2f})")
        print("=" * 60)

        return {
            "total_trades": len(self.trades),
            "win_rate": len(wins) / len(self.trades) * 100 if self.trades else 0,
            "total_pnl_pct": total_pnl_pct,
            "max_drawdown_pct": round(max_dd * 100, 2),
            "profit_factor": sum(t["pnl_usdt"] for t in wins) / abs(sum(t["pnl_usdt"] for t in losses)) if losses else float("inf"),
            "halted": self.halted,
        }


def main():
    print("连接 OKX 获取历史数据...")
    exchange = ccxt.okx({
        "proxies": {"http": API_PROXY, "https": API_PROXY},
    })

    # 分批拉取几个月的数据
    print(f"拉取 {FETCH_DAYS} 天 {TIMEFRAME} 数据...")
    closes, candles = fetch_all_data(exchange, SYMBOL, TIMEFRAME, FETCH_DAYS)

    print(f"共 {len(closes)} 根 K 线")
    print(f"价格范围: {closes.min():.1f} ~ {closes.max():.1f}")
    print(f"时间范围: {datetime.fromtimestamp(candles[0][0]/1000)} ~ {datetime.fromtimestamp(candles[-1][0]/1000)}")
    print()

    bt = Backtest(closes, candles)
    bt.run()
    stats = bt.report()

    # 保存结果
    out = {
        "params": {
            "symbol": SYMBOL, "timeframe": TIMEFRAME, "rsi_period": RSI_PERIOD,
            "rsi_oversold": RSI_OVERSOLD, "rsi_overbought": RSI_OVERBOUGHT,
            "ema_fast": EMA_FAST, "ema_slow": EMA_SLOW,
            "take_profit": TAKE_PROFIT_PCT, "stop_loss": STOP_LOSS_PCT,
            "trailing_stop": TRAILING_STOP_PCT,
            "position_usdt": POSITION_USDT, "max_drawdown": MAX_DRAWDOWN_PCT,
        },
        "stats": stats,
        "trades": bt.trades,
    }
    with open("e:/claude code files/backtest_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存: backtest_result.json")


if __name__ == "__main__":
    main()
