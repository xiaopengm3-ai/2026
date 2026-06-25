import json

d = json.load(open(r'e:\claude code files\策略研究\crypto-trend-following\backtest\results\backtest_result.json', 'r', encoding='utf-8'))
trades = d.get('backtest', d).get('trades', d.get('trades', []))

print(f"{'#':>3} {'Entry':>12} {'Exit':>12} {'Reason':<22} {'PnL':>10} {'PnL%':>8} {'Hold':>5}")
print("-" * 80)

total_pnl = 0
wins = 0
losses = 0
for t in trades:
    total_pnl += t['pnl']
    if t['pnl'] > 0:
        wins += 1
    else:
        losses += 1
    print(f"T{t['trade_id']:<2} {t['entry_time'][:10]:>12} {t['exit_time'][:10]:>12} {t['exit_reason']:<22} {t['pnl']:>+9.2f} {t['pnl_pct']:>+7.1f}% {t['hold_bars']:>4}d")

print("-" * 80)
print(f"Total PnL: ${total_pnl:,.2f} | Wins: {wins} | Losses: {losses} | Win Rate: {wins/len(trades)*100:.1f}%" if trades else "No trades")
