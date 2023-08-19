import pandas as pd
import numpy as np

import time

import requests
from bs4 import BeautifulSoup

import zipfile
from io import BytesIO


class PublicData:
    def __init__(self):
        self.freq = 0
        self.header = {"User-Agent": "Mozilla/5.0"}


    def set_freq(self, freq):
        """time sleep 값 설정"""
        self.freq = freq
        print(f'Set freq: {freq}')
        return True
    
    
    def get_usdt_tickers(self):
        """바이낸스 선물 지원 티커들 반환"""
        url = 'https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/daily/klines/'
        params = {
            "delimiter": "/",
            "prefix": "data/futures/um/daily/klines/"
        }

        html = requests.get(url=url, params=params, headers=self.header).text
        bs = BeautifulSoup(html, 'lxml')

        tickers = []
        for dir_ in bs.find_all('prefix')[1:]:
            dir_ = str(dir_).split('/')
            ticker = dir_[5]
            if ticker[-4:] == 'USDT':
                tickers.append(ticker)
        return tickers
    
    
    def get_kline(self, symbol, start, end):
        """start부터 end까지 기간의 symbol OHLCV 반환"""
        dates = pd.date_range(start=start, end=end, freq='D')
        col = ['open', 'high', 'low', 'close', 'volume']
        df = pd.DataFrame(index=dates, columns=col)
        df.index = df.index.strftime('%Y-%m-%d')
        
        for date in df.index:
            url = f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1d/{symbol}-1d-{date}.zip"
            resp = requests.get(url)
            z = zipfile.ZipFile(BytesIO(resp.content))
            z.extractall(f"USDT/{symbol}")
            
            temp_df = pd.read_csv(f'USDT/{symbol}/{symbol}-1d-{date}.csv')
            df.loc[date,:] = temp_df.values[0][1:6]
            print(f'{date} / {end}', end='\r')
            time.sleep(self.freq)
        return df             

    
    