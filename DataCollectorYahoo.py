import yfinance as yf
import datetime

symbol = "EURUSD=X"

start = datetime.datetime(2023, 4, 23, 0, 00, 0)
end = datetime.datetime(2023, 6, 21, 10, 00, 0)

data = yf.download(symbol, start=start, end=end, interval="5m")
print(data)

num_candles = len(data)
print(num_candles)