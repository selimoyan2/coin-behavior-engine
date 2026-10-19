import pandas as pd

df = pd.read_parquet('research_outputs/market_state_dataset.parquet')

init_capital = 10000.0
alloc_pct = 0.98
alloc_usdt = init_capital * alloc_pct # 9800.0
cash_reserve = init_capital - alloc_usdt # 200.0

fee_rate = 0.0010
slip_rate = 0.0005

# -----------------
# 1. Bar 0 Inception
# -----------------
b0_open = df.iloc[0]['open']
b0_entry_fill = b0_open * (1.0 + slip_rate)
b0_entry_fee = alloc_usdt * fee_rate
b0_net_invested = alloc_usdt - b0_entry_fee
b0_btc = b0_net_invested / b0_entry_fill

term_close = df.iloc[-1]['close']
# Mark to Market
b0_mtm_equity = cash_reserve + (b0_btc * term_close)
b0_mtm_ret = (b0_mtm_equity - init_capital) / init_capital * 100.0

# Liquidated
b0_exit_fill = term_close * (1.0 - slip_rate)
b0_gross_exit = b0_btc * b0_exit_fill
b0_exit_fee = b0_gross_exit * fee_rate
b0_net_exit = b0_gross_exit - b0_exit_fee
b0_liquid_equity = cash_reserve + b0_net_exit
b0_liquid_ret = (b0_liquid_equity - init_capital) / init_capital * 100.0

print('--- BAR 0 INCEPTION ---')
print(f"Start: {df.iloc[0]['datetime_utc']} @ {b0_open:.2f}")
print(f"End:   {df.iloc[-1]['datetime_utc']} @ {term_close:.2f}")
print(f"BTC Qty: {b0_btc:.8f}")
print(f"Entry Fee: {b0_entry_fee:.2f}, Entry Slip: {alloc_usdt * slip_rate:.2f}")
print(f"Exit Fee:  {b0_exit_fee:.2f}, Exit Slip:  {b0_btc * term_close * slip_rate:.2f}")
print(f"Terminal MTM Equity: {b0_mtm_equity:.2f} ({b0_mtm_ret:.2f}%)")
print(f"Terminal Liquid Equity: {b0_liquid_equity:.2f} ({b0_liquid_ret:.2f}%)")

# -----------------
# 2. Bar 576 Inception (Post-Warmup)
# -----------------
b576_open = df.iloc[576]['open']
b576_entry_fill = b576_open * (1.0 + slip_rate)
b576_entry_fee = alloc_usdt * fee_rate
b576_net_invested = alloc_usdt - b576_entry_fee
b576_btc = b576_net_invested / b576_entry_fill

# Mark to Market
b576_mtm_equity = cash_reserve + (b576_btc * term_close)
b576_mtm_ret = (b576_mtm_equity - init_capital) / init_capital * 100.0

# Liquidated
b576_exit_fill = term_close * (1.0 - slip_rate)
b576_gross_exit = b576_btc * b576_exit_fill
b576_exit_fee = b576_gross_exit * fee_rate
b576_net_exit = b576_gross_exit - b576_exit_fee
b576_liquid_equity = cash_reserve + b576_net_exit
b576_liquid_ret = (b576_liquid_equity - init_capital) / init_capital * 100.0

print('\n--- BAR 576 INCEPTION ---')
print(f"Start: {df.iloc[576]['datetime_utc']} @ {b576_open:.2f}")
print(f"End:   {df.iloc[-1]['datetime_utc']} @ {term_close:.2f}")
print(f"BTC Qty: {b576_btc:.8f}")
print(f"Entry Fee: {b576_entry_fee:.2f}, Entry Slip: {alloc_usdt * slip_rate:.2f}")
print(f"Exit Fee:  {b576_exit_fee:.2f}, Exit Slip:  {b576_btc * term_close * slip_rate:.2f}")
print(f"Terminal MTM Equity: {b576_mtm_equity:.2f} ({b576_mtm_ret:.2f}%)")
print(f"Terminal Liquid Equity: {b576_liquid_equity:.2f} ({b576_liquid_ret:.2f}%)")
