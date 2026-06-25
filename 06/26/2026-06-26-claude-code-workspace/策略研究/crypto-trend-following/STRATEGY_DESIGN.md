# 双均线+RSI过滤 趋势跟踪策略 (Dual-MA Crossover with RSI Filter) — 策略设计文档

> 本文档是策略的精确设计规格，供 AI 生成代码时读取。
> 设计路径: **诊断路径** — 用户需求不明确，从最通用的方向开始。

---

## 0. 项目文件说明
```
crypto-trend-following/
  ├── STRATEGY_DESIGN.md    ← 策略的施工图纸（本文件）
  ├── strategy.py           ← 策略核心代码（Phase 2 生成）
  ├── config.yaml           ← 参数配置文件（Phase 2 生成）
  ├── requirements.txt      ← Python 依赖（Phase 2 生成）
  ├── data/
  │   ├── fetch_data.py     ← 获取 Binance 历史K线数据（Phase 2 生成）
  │   └── ETHUSDT_1d.csv    ← 历史K线数据文件
  └── backtest/
      ├── backtest_engine.py ← 回测引擎（Phase 2 生成）
      └── results/
          └── *.json        ← 回测结果输出
```

---

## 1. 策略元信息
| 字段 | 值 |
|------|---|
| 策略名称 | 双均线+RSI过滤 趋势跟踪策略 |
| 策略简称 | DualMA_Trend |
| 策略类型 | 趋势跟踪 + 杠杆 (Leveraged Trend Following) |
| 适用市场 | Cryptocurrency / Binance Perpetual Futures |
| 适用品种 | ETH/USDT |
| 数据周期 | 日线 (Daily / 1d) |
| 设计路径 | 诊断路径 (用户需求模糊，从最通用方向切入) |
| 设计哲学 | 2x杠杆放大趋势收益；止损先于强平触发 |

---

## 2. 交易模式

| 参数 | 值 | 说明 |
|------|---|------|
| 交易标的 | ETH/USDT 永续 | Binance Futures |
| 杠杆倍数 | 2x | 可控 1-5x |
| 保证金模式 | 逐仓 Isolated | 单笔风险隔离 |
| 资金费率 | ~8% 年化 | 多头支付，计入成本 |
| 手续费 | 0.04% taker | 开平各收一次 |

**合约 vs 现货：**
- 现货: 0,000 买 ,000 ETH → 涨 50% → 赚 ,000 (+10%)
- 合约: 00 保证金 → 开 ,000 名义 (2x) → 涨 50% → 赚 ,000 (+10%)
- 区别: 只占 00 而非 ,000，剩余资金闲置
- 安全: 2x 强平线 ~-50%，ATR 止损 -10~15%，止损远在强平之前

## 3. 策略概述

### 3.1 策略逻辑简述
使用两条不同周期的简单移动平均线(SMA)的交叉作为趋势判断信号。当短期均线上穿长期均线(金叉)时，视为上升趋势启动，产生买入信号。当短期均线下穿长期均线(死叉)时，视为趋势结束，产生卖出信号。

为减少震荡市中的假信号，引入 RSI 作为过滤条件：仅在 RSI 不处于超买区(<70)时允许买入。同时引入 ATR 动态止损和时间止损来保护本金。

### 3.2 为什么选择此策略
1. **简单可靠**: 均线交叉是最经典的趋势跟踪方法，逻辑透明，不易过拟合。
2. **适合加密市场**: 加密资产具有强趋势特性(2020-2021牛市, 2022熊市, 2023-2024复苏)。双向交易可同时捕捉上涨和下跌趋势。
3. **日线级别**: 避免日内噪音，减少交易频率和手续费损耗。
4. **ETH/USDT**: 流动性最强的交易对之一，波动适中，数据完整。
5. **双向交易**: 做多+做空，熊市不再空仓等待，下跌趋势中也能获利。

### 3.3 备选策略方向 (供后续探索)
| 方向 | 适用场景 | 复杂度 |
|------|---------|--------|
| 均值回归(Bollinger Bands + RSI) | 震荡市 | 中 |
| 网格交易(区间震荡) | 横盘市 | 低 |
| 动量突破(Donchian Channel) | 强趋势市 | 中 |

---

## 4. 指标定义

### 3.1 指标 1: 短期简单移动平均线 (SMA_FAST)
- **数学公式**: `SMA_FAST[t] = sum(CLOSE[t-N+1:t+1]) / N`
- **参数名**: `sma_fast_period`
- **默认值**: `20`
- **值域/合理范围**: `[10, 50]`
- **优化搜索步长** (仅参考, 实际待 Phase 3 决定): `5`
- **数据类型**: `float`, 保留 2 位小数
- **计算前提**: 至少 N 根K线。当可用K线不足 N 时，该指标为 `NaN`。
- **在持仓期间行为**: 持续计算，不做特殊处理。

### 3.2 指标 2: 长期简单移动平均线 (SMA_SLOW)
- **数学公式**: `SMA_SLOW[t] = sum(CLOSE[t-N+1:t+1]) / N`
- **参数名**: `sma_slow_period`
- **默认值**: `50`
- **值域/合理范围**: `[30, 100]`
- **优化搜索步长**: `10`
- **数据类型**: `float`, 保留 2 位小数
- **计算前提**: 至少 N 根K线。当可用K线不足 N 时，该指标为 `NaN`。
- **在持仓期间行为**: 持续计算，不做特殊处理。

### 3.3 指标 3: 相对强弱指数 (RSI)
- **数学公式**:
  ```
  RS = avg_gain(period) / avg_loss(period)
  RSI = 100 - 100 / (1 + RS)
  ```
  其中 avg_gain 和 avg_loss 使用 Wilder 平滑法 (等效于 EMA):
  ```
  avg_gain[t] = (avg_gain[t-1] * (period-1) + gain[t]) / period
  avg_loss[t] = (avg_loss[t-1] * (period-1) + loss[t]) / period
  ```
  首次初始化时使用 N 周期的简单平均。
- **参数名**: `rsi_period`
- **默认值**: `14`
- **值域**: `[0, 100]`
- **数据类型**: `float`, 保留 2 位小数
- **计算前提**: 至少 period*2 根K线用于稳定初始化。
- **在持仓期间行为**: 持续计算。仅用于开仓过滤，不参与持仓期间的卖出决策。

### 3.4 指标 4: 平均真实波幅 (ATR)
- **数学公式**:
  ```
  TR[t] = max(high[t] - low[t],
              |high[t] - close[t-1]|,
              |low[t] - close[t-1]|)
  ATR[t] = EMA(TR, period)  或 SMA(TR, period)
  ```
  使用 SMA 平滑方式（与均线计算保持一致）。
- **参数名**: `atr_period`
- **默认值**: `14`
- **值域/合理范围**: 不固定，取决于价格水平。
- **数据类型**: `float`, 保留 2 位小数
- **计算前提**: 至少 period+1 根K线 (TR需要前一收盘价)。
- **在持仓期间行为**: 持续计算。用于动态止损和计算止损价格。

### 3.5 指标计算顺序
在每根K线上，按以下顺序计算指标（保证依赖关系）：
1. TR (依赖 high, low, prev_close)
2. ATR (依赖 TR)
3. SMA_FAST (依赖 close)
4. SMA_SLOW (依赖 close)
5. RSI (依赖 close 变化)

---

## 5. 信号逻辑

### 4.1 信号概述
| 信号类型 | 触发逻辑 | 条件关系 | 优先级 |
|---------|---------|---------|--------|
| BUY | 多条件 AND | 全部满足 | 2 (低于止损) |
| SELL_DEATH_CROSS | 死叉 | 满足即触发 | 3 |
| SELL_STOP_LOSS | 价格跌破止损线 | 满足即触发 | 1 (最高) |
| SELL_TIME_STOP | 持仓超时+收益不达标 | 满足即触发 | 3 |

### 4.2 买入信号 (BUY)

**信号类型**: `BUY`

**触发条件** (所有条件必须同时满足, AND 逻辑):
1. `SMA_FAST[t] > SMA_SLOW[t]` — 快线在慢线之上
2. `SMA_FAST[t-1] <= SMA_SLOW[t-1]` — 前一根K线快线在慢线之下或平齐（即"金叉"刚发生）
3. `RSI[t] < 70` — 当前不处于超买状态
4. `position == 0` — 当前无持仓

**信号强度计算** (用于排序，仅多标的时使用):
- `signal_strength = (RSI - 50) / 20` (正值表示偏多，但不过热)
- 取值范围约 [-2.5, 1.0]
- 单标的交易中，只要条件满足即执行，信号强度仅做记录。

**买入数量计算**:
```
buy_quantity = (total_equity * position_ratio) / close[t]
```
结果向下取整到交易对的最小数量精度 (BTC: 5位小数, ETH: 4位小数)。

**买入价格**:
- 使用次日开盘价 `open[t+1]` (日线策略，信号在收盘后确认，次根K线开盘执行)。

**极端场景处理**:
- 如果计算出的 `buy_quantity < min_notional` (Binance最小名义价值，BTC约10 USDT)，则忽略本次信号。
- 如果 `total_equity < 100 USDT`，不再开仓（防止资金过度碎片化）。
- 如果连续出现3个买入信号（持续金叉且RSI未超买），忽略后续信号（防止在趋势中途反复加仓 — 本策略仅开仓一次，平仓后重新等待信号）。

### 4.3 卖出信号 (SELL)

#### 4.3.1 死叉卖出 (SELL_DEATH_CROSS)
**信号类型**: `SELL_DEATH_CROSS`
**触发条件** (满足任一即触发, OR 逻辑):
- `SMA_FAST[t] < SMA_SLOW[t]` AND `SMA_FAST[t-1] >= SMA_SLOW[t-1]` (死叉刚发生)
- `position > 0` — 当前有持仓

**卖出价格**: 使用次日开盘价 `open[t+1]`。

#### 4.3.2 止损卖出 (SELL_STOP_LOSS)
**信号类型**: `SELL_STOP_LOSS`
**优先级**: **最高** — 在所有卖出条件中优先检查。

**触发条件**:
- `position > 0` — 当前有持仓
- `low[t] <= stop_loss_price` (日内最低价触及止损价)

**止损价格计算**:
```
stop_loss_price = entry_price - atr_multiplier * ATR[entry_bar]
```
- `atr_multiplier` 默认值: `2.0`
- `entry_price`: 买入成交价
- `ATR[entry_bar]`: 买入当根K线的ATR值（买入时锁定，不随持仓期间变化）

**止损价格更新规则**:
- 止损价**不移动**。一旦设定，始终使用买入时的ATR计算的止损价。
- 后续可以考虑移动止损（追踪止损），但当前版本不启用，保持简单。

**卖出价格**: 以 `stop_loss_price` 卖出。如果 `open[t] <= stop_loss_price` (跳空跌破)，以 `open[t]` 卖出。

**三重确认**:
1. `low[t] <= stop_loss_price` (价格触及)
2. `position > 0` (有持仓)
3. 已持有至少 1 根K线 (避免买入当日立即止损，因为买入在开盘执行)

#### 4.3.3 时间止损卖出 (SELL_TIME_STOP)
**信号类型**: `SELL_TIME_STOP`

**触发条件** (所有条件必须同时满足):
- `position > 0` — 当前有持仓
- `hold_bars >= time_stop_bars` — 持仓K线数达到阈值
- `(close[t] - entry_price) / entry_price < time_stop_return` — 累计收益不达标

**参数**:
- `time_stop_bars`: 默认 `60` (约3个月日线)
- `time_stop_return`: 默认 `0.02` (2%)

**设计意图**: 如果持仓3个月连2%都没赚到，说明趋势判断错误或市场进入震荡，应释放资金。

**卖出价格**: 使用次日开盘价 `open[t+1]`。

### 4.4 做空信号 (SHORT)

#### 4.4.1 做空入场 (SHORT_ENTRY)
**信号类型**: `SHORT_ENTRY`

**触发条件** (所有条件必须同时满足, AND 逻辑):
1. `SMA_FAST[t] < SMA_SLOW[t]` — 快线在慢线之下
2. `SMA_FAST[t-1] >= SMA_SLOW[t-1]` — 前一根K线快线在慢线之上或平齐（即"死叉"刚发生）
3. `RSI[t] > 30` — 当前不处于超卖状态
4. `position == 0` — 当前无持仓

**做空数量计算**: 同做多，使用总资金 * position_ratio。

**做空价格**: 使用次日开盘价 `open[t+1]`。

#### 4.4.2 做空离场 (SHORT_EXIT)
**触发条件** (满足任一即触发, OR 逻辑):

**死叉反向（金叉）离场**:
- `SMA_FAST[t] > SMA_SLOW[t]` AND `SMA_FAST[t-1] <= SMA_SLOW[t-1]` (金叉刚发生)
- `position < 0` — 当前有空头持仓

**止损离场** (优先级最高):
- `position < 0` — 当前有空头持仓
- `high[t] >= stop_loss_price` (日内最高价触及空头止损价)
- 止损价计算: `stop_loss_price = entry_price + atr_multiplier * ATR[entry_bar]`
- 空头止损不移动

**时间止损**:
- `position < 0` AND `hold_bars >= time_stop_bars`
- `(entry_price - close[t]) / entry_price < time_stop_return` — 做空收益不达标

#### 4.4.3 做空信号优先级
在同一根K线上，按以下优先级处理：
1. 空头止损 > 多头止损（先平仓后判断）
2. 时间止损 > 死叉/金叉信号
3. 金叉离场（空头平仓）
4. 死叉入场（空头开仓）

### 4.5 信号优先级规则（全局）
在同一根K线上，按以下优先级处理：
1. **止损卖出 (SELL_STOP_LOSS)** — 最高优先级，先于一切
2. **时间止损卖出 (SELL_TIME_STOP)**
3. **死叉卖出 (SELL_DEATH_CROSS)**
4. **买入 (BUY)** — 最低优先级

**互斥规则**:
- 同一根K线内**不允许**双向操作。如果既有卖出又有买入信号，只执行优先级更高的。
- 执行任意卖出后，本K线不再检查买入信号。
- 卖出信号之间也互斥：如果已触发止损，不再检查时间止损和死叉。

### 4.5 信号禁止清单
以下情况**禁止生成任何信号**：
- `SMA_FAST` 或 `SMA_SLOW` 为 `NaN` (指标未就绪)
- `RSI` 为 `NaN`
- `ATR` 为 `NaN`
- `close[t]` <= 0 (无效数据)
- 成交量 `volume[t]` == 0 (异常K线)

---

## 6. 仓位管理

### 5.1 仓位计算方法
- **方法**: 固定比例仓位 (Fractional Position Sizing)
- **公式**: `position_value = total_equity * position_ratio`
- **参数**: `position_ratio` 默认 `0.20` (每次使用总资金的 20%)
- **单标的仓位上限**: 总资金的 `0.30` (30%)

### 5.2 加仓规则
- **当前版本**: 不加仓。一次只持有一个仓位，平仓后再等待下一次信号。
- **未来扩展**: 可考虑盈利加仓 (Pyramiding)，但当前保持简单。

### 5.3 减仓规则
- 不进行部分减仓。卖出即全部平仓。

### 5.4 满仓处理
- 如果 `总仓位 >= 总资金的 80%` (多标的场景，当前版本不适用)，不再开新仓。

---

## 7. 风控规则

| 编号 | 规则 | 阈值 | 触发动作 |
|------|------|------|---------|
| RC-1 | 单笔最大仓位 | 总资金的 30% | 买入时限制 quantity |
| RC-2 | 单笔最大亏损 | 买入金额的 8% | ATR 止损卖出 (ATR multiplier=2.0) |
| RC-3 | 总仓位上限 | 总资金的 80% | 不再开新仓 |
| RC-4 | 最大回撤容忍 | 峰值权益的 20% | 全部清仓，暂停交易 |
| RC-5 | 连亏保护 | 连续亏损 3 笔 | 仓位比例减半 (0.20 -> 0.10) |
| RC-6 | 最小资金门槛 | 剩余资金 < 100 USDT | 不交易 |

### 6.1 最大回撤止损 (RC-4) 详细说明
- 记录历史峰值权益 `peak_equity`。
- 每次计算 `drawdown = (peak_equity - current_equity) / peak_equity`。
- 当 `drawdown >= 0.20` (20%) 时，立即清空所有持仓，并将策略状态设为 `PAUSED`。
- 策略恢复条件: 暂不自动恢复，需人工介入判断。

### 6.2 连亏保护 (RC-5) 详细说明
- 维护一个 `consecutive_losses` 计数器。
- 每次平仓如果是亏损（平仓价值 < 开仓成本），计数器 +1。
- 每次平仓如果是盈利，计数器重置为 0。
- 当 `consecutive_losses >= 3` 时，`position_ratio` 从 0.20 降至 0.10。
- 当再次盈利后，`position_ratio` 恢复为 0.20。

---

## 8. 回测参数

| 参数 | 值 | 说明 |
|------|---|------|
| 初始资金 (initial_capital) | 10,000 USDT | 回测起始资金 |
| 基准货币 (base_currency) | USDT | 计价单位 |
| 手续费率 (fee_rate) | 0.10% (0.001) | Binance 现货 maker/taker 费率 |
| 滑点 (slippage) | 0.05% (0.0005) | BTC/ETH 流动性极好，滑点很小 |
| 最小名义价值 (min_notional) | 10.0 USDT | Binance 最小交易金额 |
| 回测起始日期 | 2020-01-01 | 覆盖一轮完整牛熊 |
| 回测结束日期 | 2025-12-31 | 覆盖当前周期 |
| K线周期 | 1d (日线) | |
| 数据源 | Binance Public API | GET /api/v3/klines |
| 无风险利率 | 0% | 加密市场无无风险收益率基准 |

### 7.1 滑点模型
```
成交价格 = 信号价格 * (1 + slippage)  # 买入
成交价格 = 信号价格 * (1 - slippage)  # 卖出
```
简化处理：不区分 maker/taker，统一按 taker 费率。

### 7.2 数据要求
- 至少需要 `max(sma_slow_period, rsi_period*2, atr_period+1) = max(50, 28, 15) = 50` 根K线作为预热期。
- 回测从预热期结束后开始生成信号。
- 数据字段: `[timestamp, open, high, low, close, volume]` (CSV 格式，与 Binance klines 一致)。

---

## 9. 策略状态机

```
      ┌──────────┐
      │  IDLE    │  (无持仓，等待信号)
      └────┬─────┘
           │ 金叉 → BUY / 死叉 → SHORT_ENTRY
           ▼
      ┌──────────┐     ┌──────────┐
      │  LONG    │     │  SHORT   │
      └────┬─────┘     └────┬─────┘
           │ SELL 信号       │ EXIT 信号
           ▼                 ▼
      ┌──────────┐     ┌──────────┐
      │  IDLE    │     │  IDLE    │
      └──────────┘     └──────────┘
      
  异常路径:
  IDLE/LONG/SHORT ──(回撤>20%)──> PAUSED (暂停交易)
```

### 8.1 状态定义
| 状态 | 描述 | 允许操作 |
|------|------|---------|
| IDLE | 空仓等待中 | 检查 BUY 和 SHORT_ENTRY 信号 |
| LONG | 持有多头仓位 | 检查多头 SELL 信号 |
| SHORT | 持有空头仓位 | 检查空头 EXIT 信号 |
| PAUSED | 触发风控熔断 | 不交易，等待人工恢复 |

### 8.2 状态数据
每个状态需要维护的数据：
- **全局**: `total_equity`, `available_cash`, `peak_equity`, `consecutive_losses`, `total_trades`, `position_ratio`
- **持仓期**: `position_size`, `entry_price`, `entry_bar`, `stop_loss_price`, `hold_bars`

---

## 10. 交易记录

### 9.1 每笔交易需记录的字段
| 字段 | 类型 | 说明 |
|------|------|------|
| trade_id | int | 交易序号 (从1开始) |
| entry_time | datetime | 买入时间 (K线时间戳) |
| exit_time | datetime | 卖出时间 (K线时间戳) |
| entry_price | float | 买入成交价 |
| exit_price | float | 卖出成交价 |
| exit_reason | str | SELL_DEATH_CROSS / SELL_STOP_LOSS / SELL_TIME_STOP |
| quantity | float | 交易数量 |
| pnl | float | 绝对盈亏 (USDT) |
| pnl_pct | float | 百分比盈亏 |
| commission | float | 总手续费 (买入+卖出) |
| hold_bars | int | 持仓K线数 |
| max_profit_pct | float | 持仓期间最大浮盈百分比 |
| max_loss_pct | float | 持仓期间最大浮亏百分比 |

---

## 11. 禁止事项

1. **禁止使用未来数据**: 所有信号判断只能使用 `t` 时刻及之前的数据。指标计算、信号触发、止损检查均以收盘价确认为准。
2. **禁止忽略手续费和滑点**: 每笔交易必须扣除 0.1% 手续费(买卖各一次)和 0.05% 滑点。
3. **禁止修改信号优先级**: 止损 > 时间止损 > 死叉 > 买入。代码中必须严格按此顺序检查。
4. **禁止在指标未就绪时产生信号**: 预热期内及任何指标为 NaN 时，不生成任何交易信号。
5. **禁止对同一根K线执行多次操作**: 每根K线最多产生一次交易动作（买入或卖出，不能同时）。
6. **禁止使用收盘价直接作为成交价**: 日线信号的成交价必须为次日开盘价，止损除外(盘中触发)。

---

## 12. 已知局限

1. **震荡市表现差**: 均线交叉策略在横盘震荡市场会频繁产生假信号，导致连续小额亏损。这是趋势跟踪类策略的固有缺陷，只能通过仓位控制和连亏保护来缓解，无法根本消除。
2. **滞后性**: 均线是滞后指标，金叉/死叉信号通常发生在趋势已经开始或结束之后，会错过趋势的前端和后端利润。
3. **未考虑极端事件**: 如交易所宕机、312 暴跌、LUNA 崩盘等黑天鹅事件。实际运行时应配合人工监控。
4. **现货做空限制**: Binance现货不支持直接做空，需用逐仓杠杆或合约。本策略假设支持做空机制（如逐仓杠杆借币卖出）。
5. **不捕捉日内波动**: 基于日线收盘价决策，日内大幅波动仅在触及止损线时才反应。
6. **ATR止损不移动**: 止损价在买入时固定，不随价格上涨而上移。在强趋势中可能过早止盈出局，在震荡中可能止损过宽。
7. **滑点模型简化**: 固定比例滑点不考虑市场深度和订单簿冲击，大资金实盘时需调整。
8. **Binance API限制**: 免费API有请求频率限制(1200次/分钟)，获取大量历史数据时需注意速率控制。

---

## 13. 参数汇总

| 参数名 | 默认值 | 值域 | 说明 |
|--------|--------|------|------|
| sma_fast_period | 20 | [10, 50] | 短期均线周期 |
| sma_slow_period | 50 | [30, 100] | 长期均线周期 |
| rsi_period | 14 | [7, 21] | RSI 计算周期 |
| atr_period | 14 | [7, 21] | ATR 计算周期 |
| atr_multiplier | 2.0 | [1.5, 3.0] | 止损ATR倍数 |
| rsi_buy_threshold | 70 | [60, 80] | 买入RSI上限 |
| time_stop_bars | 60 | [30, 120] | 时间止损K线数 |
| time_stop_return | 0.02 | [0.0, 0.05] | 时间止损收益阈值 |
| position_ratio | 0.20 | [0.10, 0.50] | 单笔仓位比例 |
| max_equity_drawdown | 0.20 | [0.10, 0.30] | 最大回撤容忍 |
| max_consecutive_losses | 3 | [2, 5] | 连亏保护阈值 |
| initial_capital | 10000 | - | 回测初始资金 |
| fee_rate | 0.001 | - | 手续费率 |
| slippage | 0.0005 | - | 滑点率 |

---

## 14. 策略评价指标 (回测输出)

回测完成后应输出以下指标：

| 指标 | 公式/说明 |
|------|----------|
| 总收益率 | `(final_equity - initial_capital) / initial_capital` |
| 年化收益率 | `(1 + total_return)^(365/total_days) - 1` |
| 最大回撤 | `max((peak_equity - trough_equity) / peak_equity)` |
| 夏普比率 | `(annual_return - risk_free_rate) / annual_volatility` (risk_free_rate=0) |
| 胜率 | `winning_trades / total_trades` |
| 盈亏比 | `avg_profit_per_winner / avg_loss_per_loser` (取绝对值) |
| 交易次数 | `total_trades` |
| 年均交易次数 | `total_trades / (total_days / 365)` |
| 最大连亏次数 | `max_consecutive_losses_actual` |
| 手续费总额 | `sum(all_commissions)` |
| 收益/费用比 | `total_pnl / total_commission` |

---

## 15. 下一步

等待用户审查并确认 STRATEGY_DESIGN.md 后，进入 **Phase 2**：
1. 生成 `requirements.txt` (ccxt, pandas, numpy, pyyaml, matplotlib)
2. 生成 `config.yaml` (从本文档参数汇总提取)
3. 生成 `data/fetch_data.py` (通过 ccxt 从 Binance 获取历史K线)
4. 生成 `strategy.py` (核心策略逻辑，严格按本文档实现)
5. 生成 `backtest/backtest_engine.py` (回测引擎)
6. 跑回测并输出结果
