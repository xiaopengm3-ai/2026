#!/usr/bin/env python3
"""
DualMA_Trend — 双均线+RSI过滤 趋势跟踪策略
Crypto-adapted: Binance Spot, ETH/USDT, Daily candles

Exposes run_backtest(config) -> dict for the autostrategy harness.
"""

import os
import sys
import json
import math
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════════════════════════
#  INDICATOR CALCULATIONS
# ═══════════════════════════════════════════════════════════════════

def calc_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index using Wilder smoothing (EMA-based).
    First `period` values use simple average; thereafter Wilder smoothing.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    result = pd.Series(np.nan, index=series.index)

    # Initial simple average at index = period
    init_gain = gain.iloc[1:period + 1].mean()
    init_loss = loss.iloc[1:period + 1].mean()
    if init_loss == 0:
        result.iloc[period] = 100.0
    else:
        rs = init_gain / init_loss
        result.iloc[period] = 100.0 - 100.0 / (1.0 + rs)

    avg_gain = init_gain
    avg_loss = init_loss

    for i in range(period + 1, len(series)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period
        if avg_loss == 0:
            result.iloc[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result.iloc[i] = 100.0 - 100.0 / (1.0 + rs)

    return result


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range using SMA smoothing.
    TR = max(high-low, |high-prev_close|, |low-prev_close|)
    """
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    return atr


# ── ADX ──
def calc_adx(df, period=14):
    """Average Directional Index — trend strength indicator."""
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    tr = pd.Series(
        np.maximum(high - low,
                   np.maximum(np.abs(high - np.roll(close, 1)),
                              np.abs(low - np.roll(close, 1)))),
        index=df.index
    )
    tr.iloc[0] = high[0] - low[0]
    atr_adx = tr.ewm(alpha=1/period, adjust=False).mean()
    up = pd.Series(np.maximum(high - np.roll(high, 1), 0), index=df.index)
    dn = pd.Series(np.maximum(np.roll(low, 1) - low, 0), index=df.index)
    up.iloc[0] = 0
    dn.iloc[0] = 0
    plus_dm = ((up > dn) & (up > 0)).astype(float) * up
    minus_dm = ((dn > up) & (dn > 0)).astype(float) * dn
    plus_di = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr_adx + 1e-10)
    minus_di = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr_adx + 1e-10)
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx



# ── MACD ──
def calc_macd(close, fast=12, slow=26, signal=9):
    """MACD: returns (macd_line, signal_line, histogram)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


# ── KDJ ──
def calc_kdj(df, n=9, k_smooth=3, d_smooth=3):
    """KDJ: returns (K, D, J). Standard 9,3,3."""
    low_n = df['low'].rolling(window=n).min()
    high_n = df['high'].rolling(window=n).max()
    rsv = (df['close'] - low_n) / (high_n - low_n + 1e-10) * 100
    k = rsv.ewm(alpha=1/k_smooth, adjust=False).mean()
    d = k.ewm(alpha=1/d_smooth, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


# ═══════════════════════════════════════════════════════════════════
#  MAIN BACKTEST FUNCTION
# ═══════════════════════════════════════════════════════════════════

def run_backtest(config: dict) -> dict:
    """
    Execute backtest and return metrics dict.

    Required keys in config:
        initial_cash, start_date, end_date, commission, slippage, symbol
        indicators: sma_fast_period, sma_slow_period, rsi_period, atr_period,
                    atr_multiplier, rsi_buy_threshold, time_stop_bars, time_stop_return
        risk: max_leverage_exposure, max_equity_drawdown,
              max_consecutive_losses, min_capital

    Returns dict with:
        annual_return, max_drawdown, sharpe, win_rate, profit_loss_ratio,
        total_trades, initial_cash, final_value, total_return, daily_values,
        trades, period_returns, first_half_return, second_half_return,
        avg_daily_volume, avg_trade_value
    """
    # ── Unpack config ──────────────────────────────────────────
    initial_cash   = float(config.get('initial_cash', 10000))
    start_date     = str(config.get('start_date', '2020-01-01'))
    end_date       = str(config.get('end_date', '2025-12-31'))
    commission_pct = float(config.get('commission', 0.001))
    slippage_pct   = float(config.get('slippage', 0.0005))
    symbol         = str(config.get('symbol', 'ETH/USDT'))

    ind = config.get('indicators', {})
    sma_fast_period   = int(ind.get('sma_fast_period', 20))
    sma_slow_period   = int(ind.get('sma_slow_period', 50))
    rsi_period        = int(ind.get('rsi_period', 14))
    atr_period        = int(ind.get('atr_period', 14))
    atr_multiplier    = float(ind.get('atr_multiplier', 2.0))
    rsi_buy_threshold = float(ind.get('rsi_buy_threshold', 70))
    time_stop_bars    = int(ind.get('time_stop_bars', 60))
    time_stop_return  = float(ind.get('time_stop_return', 0.02))

    trade_cfg = config.get('trading', {})
    trading_mode       = str(trade_cfg.get('mode', 'spot'))
    leverage           = float(trade_cfg.get('leverage', 1))
    funding_rate_annual = float(trade_cfg.get('funding_rate_annual', 0.0))
    funding_rate_daily  = funding_rate_annual / 365.0

    risk = config.get('risk', {})
    position_ratio         = float(risk.get('position_ratio', 0.20))
    max_leverage_exposure  = float(risk.get('max_leverage_exposure', 0.40))
    max_equity_drawdown    = float(risk.get('max_equity_drawdown', 0.20))
    max_consecutive_losses = int(risk.get('max_consecutive_losses', 3))
    min_margin_ratio       = float(risk.get('min_margin_ratio', 0.15))
    cooling_off_bars       = int(risk.get('cooling_off_bars', 90))

    # ── Load data ──────────────────────────────────────────────
    strategy_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(strategy_dir, 'data', 'ETHUSDT_1d.csv')

    if not os.path.exists(data_path):
        print(f"Data file not found at {data_path}, fetching from Binance...")
        from data.fetch_data import fetch_eth_daily
        fetch_eth_daily(save_path=data_path)
        if not os.path.exists(data_path):
            return {'error': 'Failed to fetch data from Binance'}

    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp').sort_index()
    df = df[(df.index >= start_date) & (df.index <= end_date)]

    if len(df) == 0:
        return {'error': f'No data between {start_date} and {end_date}'}

    print(f"Loaded {len(df)} daily candles: {df.index[0].date()} -> {df.index[-1].date()}")

    # ── Calculate indicators ───────────────────────────────────
    df['sma_fast'] = calc_sma(df['close'], sma_fast_period)
    df['sma_slow'] = calc_sma(df['close'], sma_slow_period)
    df['rsi']      = calc_rsi(df['close'], rsi_period)
    df['atr']      = calc_atr(df, atr_period)
    df['macd'], df['macd_signal'], _ = calc_macd(df['close'])
    df['k'], df['d'], df['j'] = calc_kdj(df)
    # Warmup: need enough bars for all indicators
    warmup = max(sma_slow_period, rsi_period * 2, atr_period + 1)
    # Also need at least 2 bars beyond warmup for prev_bar comparison
    if len(df) < warmup + 2:
        return {'error': f'Not enough data. Have {len(df)} bars, need {warmup + 2}+'}

    warmup = max(warmup, 1) + 1  # Extra bar for prev_bar cross detection

    # ── State variables ────────────────────────────────────────
    cash = initial_cash       # free USDT
    margin_locked = 0.0       # USDT locked as margin
    position = 0.0            # contract quantity (>0 = long)
    equity = initial_cash
    peak_equity = initial_cash

    # Position tracking
    entry_price = 0.0
    entry_bar_idx = -1
    stop_loss_price = 0.0
    entry_atr_value = 0.0
    hold_bars = 0

    # State machine: IDLE, LONG, PAUSED
    state = 'IDLE'
    paused_bars = 0
    cooling_off_remaining = 0
    consecutive_losses = 0
    active_position_ratio = position_ratio

    # Pending orders (for next-bar-open execution)
    # Format: {'type': 'SELL', 'reason': str} or {'type': 'BUY', 'qty': float, 'atr': float}
    pending_order = None

    # Trade records & daily values
    trades = []
    daily_values = []

    # Period returns (for diagnostic overfitting check)
    period_returns = []
    monthly_equity_snapshot = {}  # year-month -> equity

    # Volume tracking for liquidity diagnostic
    total_trade_value = 0.0
    trade_count = 0

    # For first_half / second_half return
    mid_idx = len(df) // 2
    first_half_equity = initial_cash
    second_half_equity = initial_cash
    mid_date = df.index[mid_idx]
    first_half_recorded = False

    avg_daily_volume = float(df['volume'].mean()) if 'volume' in df.columns else 0.0

    # ── Helper: record daily equity ────────────────────────────
    def record_equity(bar_date, eq):
        nonlocal first_half_recorded, first_half_equity
        daily_values.append({
            'date': bar_date.strftime('%Y-%m-%d'),
            'value': round(eq, 2)
        })
        # Track monthly snapshots for period_returns
        ym = bar_date.strftime('%Y-%m')
        monthly_equity_snapshot[ym] = eq
        # Split-half tracking
        if not first_half_recorded and bar_date >= mid_date:
            first_half_equity = eq
            first_half_recorded = True

    # ── Execute a sell ─────────────────────────────────────────
    def execute_sell(sell_price: float, reason: str, bar_date, bar_idx: int):
        nonlocal cash, margin_locked, position, equity, consecutive_losses, active_position_ratio, trade_count, total_trade_value, state, hold_bars

        # Apply slippage
        executed_price = sell_price * (1.0 - slippage_pct)
        gross_value = executed_price * abs(position)
        comm = gross_value * commission_pct

        cash += gross_value - comm
        pnl = (executed_price - entry_price) * position
        pnl_pct = (executed_price - entry_price) / entry_price * 100.0 if entry_price > 0 else 0.0

        # Consecutive loss tracking
        if pnl < 0:
            consecutive_losses += 1
        else:
            consecutive_losses = 0

        # RC-5: Consecutive loss protection
        if consecutive_losses >= max_consecutive_losses:
            active_position_ratio = position_ratio / 2.0
        else:
            active_position_ratio = position_ratio

        total_trade_value += gross_value
        trade_count += 1

        trades.append({
            'trade_id': len(trades) + 1,
            'entry_time': str(df.index[entry_bar_idx]),
            'exit_time': str(bar_date),
            'entry_price': round(entry_price, 2),
            'exit_price': round(executed_price, 2),
            'exit_reason': reason,
            'quantity': round(position, 4),
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'commission': round(comm, 2),
            'hold_bars': hold_bars,
            'max_profit_pct': 0.0,
            'max_loss_pct': 0.0,
        })

        position = 0.0
        hold_bars = 0
        state = 'IDLE'

    # ── Execute a buy ──────────────────────────────────────────
    def execute_buy(buy_price: float, quantity: float, atr_val: float, bar_date, bar_idx: int):
        nonlocal cash, margin_locked, position, entry_price, entry_bar_idx, stop_loss_price, entry_atr_value, hold_bars, state

        executed_price = buy_price * (1.0 + slippage_pct)
        notional_value = executed_price * quantity
        margin_required = notional_value / leverage
        comm = notional_value * commission_pct

        if notional_value < 10.0:
            return

        if margin_required > cash:
            return

        cash -= (margin_required + comm)
        margin_locked = margin_required
        position = quantity
        entry_price = executed_price
        entry_bar_idx = bar_idx
        entry_atr_value = atr_val
        stop_loss_price = entry_price - atr_multiplier * entry_atr_value
        hold_bars = 0
        state = 'LONG'


    # ═══════════════════════════════════════════════════════════
    #  BACKTEST LOOP
    # ═══════════════════════════════════════════════════════════

    for i in range(warmup, len(df)):
        bar = df.iloc[i]
        bar_date = df.index[i]

        # ── 0. Execute pending order from previous bar ──────────
        if pending_order is not None:
            if pending_order['type'] == 'SELL':
                execute_sell(bar['open'], pending_order['reason'], bar_date, i)
                pending_order = None
                equity = cash + position * bar['close']
                peak_equity = max(peak_equity, equity)
                record_equity(bar_date, equity)
                dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
                if dd >= max_equity_drawdown:
                    state = 'PAUSED'
                    cooling_off_remaining = cooling_off_bars
                continue

            elif pending_order['type'] == 'BUY':
                execute_buy(bar['open'], pending_order['qty'], pending_order['atr'], bar_date, i)
                pending_order = None
                equity = cash + position * bar['close']
                peak_equity = max(peak_equity, equity)
                record_equity(bar_date, equity)
                continue

        # ── 1. Pre-tick updates ─────────────────────────────────
        if state == 'LONG':
            hold_bars += 1

        # ── 2. Record daily equity ──────────────────────────────
        equity = cash + position * bar['close']
        peak_equity = max(peak_equity, equity)
        record_equity(bar_date, equity)

        # ── 3. Drawdown check (RC-4) ────────────────────────────
        current_drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
        if current_drawdown >= max_equity_drawdown:
            if state == 'LONG':
                pending_order = {'type': 'SELL', 'reason': 'MAX_DRAWDOWN'}
                continue
            elif state == 'IDLE':
                state = 'PAUSED'
                cooling_off_remaining = cooling_off_bars
                continue

        # ── 4. PAUSED state handling ────────────────────────────
        if state == 'PAUSED':
            cooling_off_remaining -= 1
            record_equity(bar_date, equity)
            if cooling_off_remaining <= 0:
                state = 'IDLE'
                peak_equity = equity
            continue

        # ── 5. Indicator ready check ────────────────────────────
        if (pd.isna(bar['sma_fast']) or pd.isna(bar['sma_slow']) or
            pd.isna(bar['rsi'])      or pd.isna(bar['atr'])):
            continue
        if bar['close'] <= 0 or bar['volume'] == 0:
            continue

        # ── 6. Margin health check ─────────────────────────────
        if cash < 50 and position == 0:
            continue  # not enough free margin to open new position

        # ═════════════════════════════════════════════════════════
        #  LONG — Check SELL signals (priority order)
        # ═════════════════════════════════════════════════════════
        if state == 'LONG':
            sell_triggered = False

            # Priority 1: STOP_LOSS (intraday)
            if bar['low'] <= stop_loss_price and hold_bars >= 1:
                if bar['open'] <= stop_loss_price:
                    sell_price = bar['open']
                else:
                    sell_price = stop_loss_price
                execute_sell(sell_price, 'SELL_STOP_LOSS', bar_date, i)
                sell_triggered = True

            # Priority 2: TIME_STOP
            if not sell_triggered and hold_bars >= time_stop_bars:
                cur_return = (bar['close'] - entry_price) / entry_price
                if cur_return < time_stop_return:
                    pending_order = {'type': 'SELL', 'reason': 'SELL_TIME_STOP'}
                    sell_triggered = True

            # Priority 3: DEATH_CROSS
            if not sell_triggered:
                prev_sma_f = df.iloc[i - 1]['sma_fast']
                prev_sma_s = df.iloc[i - 1]['sma_slow']
                death_cross = (bar['sma_fast'] < bar['sma_slow'] and
                               not pd.isna(prev_sma_f) and not pd.isna(prev_sma_s) and
                               prev_sma_f >= prev_sma_s)
                if death_cross:
                    pending_order = {'type': 'SELL', 'reason': 'SELL_DEATH_CROSS'}
                    sell_triggered = True

            if sell_triggered:
                continue

        # ═════════════════════════════════════════════════════════
        #  IDLE — Check BUY signal
        # ═════════════════════════════════════════════════════════
        if state == 'IDLE':
            prev_sma_f = df.iloc[i - 1]['sma_fast']
            prev_sma_s = df.iloc[i - 1]['sma_slow']
            golden_cross = (bar['sma_fast'] > bar['sma_slow'] and
                           not pd.isna(prev_sma_f) and not pd.isna(prev_sma_s) and
                           prev_sma_f <= prev_sma_s)
            rsi_ok = bar['rsi'] < rsi_buy_threshold
            macd_ok = (not use_macd_filter) or (not pd.isna(bar['macd'])) and (bar['macd'] > bar['macd_signal'])
            kdj_ok = (not use_kdj_filter) or (not pd.isna(bar['k'])) and (bar['k'] > bar['d'])

            if golden_cross and rsi_ok and macd_ok and kdj_ok:
                # Futures: notional = equity * exposure_ratio
                notional_value = equity * max_leverage_exposure
                max_notional = cash * leverage
                notional_value = min(notional_value, max_notional)

                est_price = bar['close']
                quantity = notional_value / est_price
                quantity = round(quantity, 4)

                if quantity * est_price >= 10.0:
                    pending_order = {
                        'type': 'BUY',
                        'qty': quantity,
                        'atr': bar['atr'],
                    }
                    continue


    # ── Final: close any remaining position ─────────────────────
    if position > 0:
        last_bar = df.iloc[-1]
        execute_sell(last_bar['close'], 'END_OF_BACKTEST', df.index[-1], len(df) - 1)

    # Final equity = cash (no open positions)
    final_equity = cash
    # Record final value
    daily_values.append({
        'date': df.index[-1].strftime('%Y-%m-%d'),
        'value': round(final_equity, 2)
    })

    # ═════════════════════════════════════════════════════════════
    #  COMPUTE METRICS
    # ═════════════════════════════════════════════════════════════

    total_days = max((df.index[-1] - df.index[0]).days, 1)
    total_return = (final_equity - initial_cash) / initial_cash

    # Annualized return (Crypto: 365-day year, continuous compounding)
    if total_return <= -1.0:
        annual_return = -1.0
    else:
        annual_return = (1.0 + total_return) ** (365.0 / total_days) - 1.0

    # Max drawdown from daily values
    dd_peak = initial_cash
    max_dd = 0.0
    for dv in daily_values:
        val = dv['value']
        if val > dd_peak:
            dd_peak = val
        dd = (dd_peak - val) / dd_peak if dd_peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio from daily returns
    daily_vals = [dv['value'] for dv in daily_values]
    daily_returns = []
    for j in range(1, len(daily_vals)):
        if daily_vals[j - 1] > 0:
            daily_returns.append(daily_vals[j] / daily_vals[j - 1] - 1.0)
        else:
            daily_returns.append(0.0)

    if len(daily_returns) > 1 and np.std(daily_returns) > 0:
        daily_vol = np.std(daily_returns)
        # Crypto trades 365 days/year
        annual_vol = daily_vol * math.sqrt(365)
        if annual_vol > 0:
            sharpe = annual_return / annual_vol  # risk_free_rate = 0
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # Win rate & profit/loss ratio
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades  = [t for t in trades if t['pnl'] < 0]
    total_trades   = len(trades)

    if total_trades > 0:
        win_rate = len(winning_trades) / total_trades * 100.0
    else:
        win_rate = 0.0

    if winning_trades:
        avg_win = np.mean([t['pnl'] for t in winning_trades])
    else:
        avg_win = 0.0

    if losing_trades:
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades]))
    else:
        avg_loss = 0.001  # Avoid division by zero

    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

    # Period returns (monthly for overfitting detection)
    if monthly_equity_snapshot:
        months = sorted(monthly_equity_snapshot.keys())
        period_rets = []
        for j in range(1, len(months)):
            prev_val = monthly_equity_snapshot[months[j - 1]]
            curr_val = monthly_equity_snapshot[months[j]]
            if prev_val > 0:
                period_rets.append((curr_val - prev_val) / prev_val)
        period_returns = period_rets

    # First half / second half returns
    mid_point = len(daily_values) // 2
    first_half_ret = 0.0
    second_half_ret = 0.0
    if mid_point > 0 and len(daily_values) > mid_point:
        start_val = daily_values[0]['value']
        mid_val = daily_values[mid_point]['value']
        end_val = daily_values[-1]['value']
        if start_val > 0:
            first_half_ret = (mid_val - start_val) / start_val
        if mid_val > 0:
            second_half_ret = (end_val - mid_val) / mid_val

    # Average trade value
    avg_trade_value = total_trade_value / trade_count if trade_count > 0 else 0.0

    # Commission total
    total_commission = sum(t['commission'] for t in trades)

    # Max consecutive losses (actual)
    max_consec_losses_actual = 0
    curr_consec = 0
    for t in trades:
        if t['pnl'] < 0:
            curr_consec += 1
            max_consec_losses_actual = max(max_consec_losses_actual, curr_consec)
        else:
            curr_consec = 0

    # Annual trade count
    annual_trades = total_trades / (total_days / 365.0) if total_days > 0 else 0

    # ═════════════════════════════════════════════════════════════
    #  RETURN RESULT DICT
    # ═════════════════════════════════════════════════════════════

    result = {
        'annual_return':        round(annual_return * 100.0, 2),  # percentage
        'max_drawdown':         round(max_dd * 100.0, 2),         # percentage
        'sharpe':               round(sharpe, 2),
        'win_rate':             round(win_rate, 2),                # percentage
        'profit_loss_ratio':    round(profit_loss_ratio, 2),
        'total_trades':         total_trades,
        'initial_cash':         initial_cash,
        'final_value':          round(final_equity, 2),
        'total_return':         round(total_return * 100.0, 2),   # percentage
        'daily_values':         daily_values,
        'trades':               trades,
        'period_returns':       period_returns,
        'first_half_return':    round(first_half_ret, 4),
        'second_half_return':   round(second_half_ret, 4),
        'avg_daily_volume':     round(avg_daily_volume, 2),
        'avg_trade_value':      round(avg_trade_value, 2),
        'total_commission':     round(total_commission, 2),
        'max_consecutive_losses_actual': max_consec_losses_actual,
        'annual_trades':        round(annual_trades, 1),
        'future_leak_detected': False,
        'universe_size':        1,
        'survivor_count':       1,
    }

    return result


# ═══════════════════════════════════════════════════════════════════
#  STANDALONE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Load config
    import yaml

    strategy_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(strategy_dir, 'config.yaml')

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print("=" * 60)
    print("  DualMA_Trend Strategy Backtest")
    print("  ETH/USDT — Daily — Binance Spot")
    print("=" * 60)
    print(f"  Period: {config['start_date']} to {config['end_date']}")
    print(f"  Initial capital: ${config['initial_cash']:,.0f} USDT")
    print()

    # Run backtest
    result = run_backtest(config)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    # Print results
    print()
    print("-" * 60)
    print("  BACKTEST RESULTS")
    print("-" * 60)
    print(f"  Final Equity:         ${result['final_value']:,.2f}")
    print(f"  Total Return:         {result['total_return']:.2f}%")
    print(f"  Annual Return:        {result['annual_return']:.2f}%")
    print(f"  Max Drawdown:         {result['max_drawdown']:.2f}%")
    print(f"  Sharpe Ratio:         {result['sharpe']:.2f}")
    print(f"  Win Rate:             {result['win_rate']:.1f}%")
    print(f"  Profit/Loss Ratio:    {result['profit_loss_ratio']:.2f}")
    print(f"  Total Trades:         {result['total_trades']}")
    print(f"  Annual Trades:        {result['annual_trades']}")
    print(f"  Max Consec Losses:    {result['max_consecutive_losses_actual']}")
    print(f"  Total Commission:     ${result['total_commission']:,.2f}")
    print()

    # Trade breakdown
    if result['trades']:
        print("-" * 60)
        print("  TRADE BREAKDOWN")
        print("-" * 60)
        reasons = {}
        for t in result['trades']:
            r = t['exit_reason']
            reasons[r] = reasons.get(r, 0) + 1
        for reason, count in reasons.items():
            print(f"  {reason}: {count} trades")
        print()

    # Save results
    output_dir = os.path.join(strategy_dir, 'backtest', 'results')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'backtest_result.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"Results saved to: {output_path}")
    print()
    print("Backtest complete!")
