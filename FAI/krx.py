import pandas as pd
import numpy as np

import re
import requests
from io import BytesIO

import time


class WebSource:
    def __init__(self):
        self.freq = 0
        self.header = {"User-Agent": "Mozilla/5.0"}
        self.codes = self.get_all_list_stocks()
        
    
    def set_freq(self, freq):
        """time sleep 값 설정"""
        self.freq = freq
        print(f'Set freq: {freq}')
        return True

    
    def get_krx_content(self, otp_params):
        """krx 크롤링 포맷: otp_params에 해당하는 데이터를 반환"""
        otp_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
        otp = requests.post(otp_url, headers=self.header, data=otp_params).text
        
        down_url = 'http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd'
        down_params = {"code": otp}
        down_content = requests.post(down_url, headers=self.header, params=down_params).content

        df = pd.read_csv(BytesIO(down_content), encoding='EUC-KR')
        time.sleep(self.freq)
        return df


    def get_index_stocks_in_period(self, index_name='KOSPI', start='2020-01-01', end='2022-12-31', universe=None):
        """universe의 종목 중 start부터 end까지 기간 동안 index_name에 포함되는 종목코드들의 값을 True로 반환"""
        if universe:
            df = pd.DataFrame(index=pd.date_range(start=start, end=end, freq='D'), columns=universe)
        else:
            df = pd.DataFrame(index=pd.date_range(start=start, end=end, freq='D'), columns=self.get_all_list_stocks())
        df.index = df.index.strftime('%Y-%m-%d')
        
        finish_day = df.index[-1]
        for date in df.index:
            cond_stocks = self.get_index_stocks(index_name=index_name, date=date)
            
            if type(cond_stocks) == bool:
                continue
            
            for cond_stock in cond_stocks:
                 if cond_stock not in df.columns:
                     df[cond_stock] = np.nan
                    
            df.loc[date, cond_stocks] = True
            
            print(f"{date} / {finish_day}", end='\r')
        
        df.dropna(how='all', axis=0, inplace=True)
        # df.fillna(False, inplace=True)
        return df


    def get_index_stocks(self, index_name='KOSPI', date='2023-08-18'):
        """date 날짜의 index_name에 포함되는 종목 코드들을 반환
        KOSPI: 1001
        KOSPI200: 1028
        KOSDAQ: 2001
        KOSDAQ150: 2203
        """
        date = date.replace('-', '')
        index_code = {
            "KOSPI":"1001",
            "KOSPI200": "1028",
            "KOSDAQ": "2001",
            "KOSDAQ150": "2203"
        }
        otp_params = {
            "indIdx": f"{index_code[index_name][0]}",
            "indIdx2": f"{index_code[index_name][1:]}",
            "trdDd": f"{date}",
            "url": "dbms/MDC/STAT/standard/MDCSTAT00601"
        }
        index_df = self.get_krx_content(otp_params)
        
        if index_df.shape[0] == 0:
            return False
        
        index_stocks = index_df['종목코드'].apply(lambda x: f'A{x:06d}').values
        return index_stocks

    
    def get_all_list_stocks(self):
        """현재 상장되어 있는 전체 종목코드 반환"""
        otp_params = {
            "mktId":"ALL",
            "trdDd": "20230801",
            "url": "dbms/MDC/STAT/standard/MDCSTAT01901"
        }
        all_list_df = self.get_krx_content(otp_params)
        all_list_df['단축코드'] = 'A' + all_list_df['단축코드']
        all_list_df.set_index('단축코드', drop=True, inplace=True)
        return all_list_df['표준코드']
    
    
    def get_ohlcv(self, stock_code, start, end):
        """start부터 end까지 기간 동안 stock_code의 OHLCV 반환"""
        start = re.sub(r'[^0-9]', '', start)
        end = re.sub(r'[^0-9]', '', end)
        stock_code = self.codes.loc[stock_code]
        
        df = pd.DataFrame()
        while start < end:
            temp_start_date = str(int(end) - 10000)
            if temp_start_date < start:
                temp_start_date = start

            otp_params = {
                "isuCd": f"{stock_code}",
                "strtDd": f"{start}",
                "endDd": f"{end}",
                "adjStkPrc_check": "Y",
                "url": "dbms/MDC/STAT/standard/MDCSTAT01701"
            }
            temp_df = self.get_krx_content(otp_params)
            df = pd.concat([df, temp_df], axis=0)
            end = str(int(temp_start_date) - 1)
        
        df = df[['일자', '시가', '고가', '저가', '종가', '거래량']]
        df.columns = ['date', 'adj_open', 'adj_high', 'adj_low', 'adj_close', 'volume']
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', drop=True, inplace=True)
        return df


    def get_index_stocks_ohlcv(self, index_name, start, end):
        """지수에 해당하는 종목들의 OHLCV 반환"""
        index_bool = self.get_index_stocks_in_period(index_name=index_name, start=start, end=end)
        
        price_dict = {}
        price_keys = ['adj_open', 'adj_high', 'adj_low', 'adj_close', 'volume']
        for k in price_keys:
            price_dict[k] = pd.DataFrame().reindex_like(index_bool)
        
        total_index_stocks = index_bool.iloc[0,:][index_bool.sum() > 1]
        total_index_stocks = total_index_stocks.index.values
        
        finish = len(total_index_stocks)
        cnt = 1
        print(' '*30)
        for stock_code in total_index_stocks:
            stock_ohlcv = self.get_ohlcv(stock_code, start, end)
            
            for k in price_keys:
                try:
                    price_dict[k].loc[start:end, stock_code] = stock_ohlcv[k].values
                except:
                    stock_start = stock_ohlcv.date.iloc[0].replace('/','-')
                    stock_end = stock_ohlcv.date.iloc[0].replace('/','-')
                    price_dict[k].loc[stock_start:stock_end, stock_code] = stock_ohlcv[k].values
            
            print(f'{cnt} / {finish}', end='\r')
            cnt += 1

        for k in price_keys:
            price_dict[k] = price_dict[k] * index_bool
        
        return price_dict