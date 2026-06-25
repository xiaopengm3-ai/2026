import ccxt
import pandas as pd
import time
import os


def fetch_eth_daily(since='2020-01-01T00:00:00Z', save_path=None):
    """
    Fetch ETH/USDT daily klines from Binance via ccxt.
    Handles rate limiting and pagination.
    Saves to CSV with columns: timestamp, open, high, low, close, volume.
    """
    exchange = ccxt.binance()
    since_ts = exchange.parse8601(since)
    end_ts = exchange.parse8601('2025-12-31T23:59:59Z')
    all_ohlcv = []

    while since_ts < end_ts:
        try:
            ohlcv = exchange.fetch_ohlcv('ETH/USDT', '1d', since=since_ts, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since_ts = ohlcv[-1][0] + 86400000  # next day
            time.sleep(0.5)
            print(f"Fetched {len(all_ohlcv)} candles, latest: {pd.to_datetime(ohlcv[-1][0], unit='ms')}")
        except Exception as e:
            print(f"Error: {e}, retrying in 5s...")
            time.sleep(5)

    if not all_ohlcv:
        print("ERROR: No data fetched from Binance!")
        return None

    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.drop_duplicates(subset='timestamp').sort_values('timestamp')

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        df.to_csv(save_path, index=False)
        print(f"Saved {len(df)} candles to {save_path}")

    return df


if __name__ == '__main__':
    # Save relative to this file's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(script_dir, 'ETHUSDT_1d.csv')
    fetch_eth_daily(save_path=save_path)
