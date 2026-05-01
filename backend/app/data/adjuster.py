import pandas as pd

class PriceAdjuster:
    """
    강화학습 모델이 주가 급락(액면분할, 배당락 등)을 손실로 착각하지 않도록 
    과거 데이터를 수정주가(Adjusted Price)로 보정하는 핵심 모듈입니다.
    데이터 프레임의 불변성(Immutability)을 지향하여 원본을 변경하지 않고 새 객체를 반환합니다.
    """
    
    PRICE_COLUMNS = ['open', 'high', 'low', 'close']
    VOLUME_COLUMN = 'volume'

    def apply_split_factor(self, df: pd.DataFrame, split_ratio: float, event_date: str) -> pd.DataFrame:
        """
        액면분할 이벤트를 반영하여 과거 주가와 거래량을 보정합니다.
        
        Args:
            df (pd.DataFrame): 과거 시계열 데이터. 인덱스는 Datetime 형식이어야 함.
            split_ratio (float): 분할 비율. (예: 5.0이면 5분의 1로 가격 하락)
            event_date (str): 액면분할 발생 기준일 (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: 보정된 새로운 시계열 데이터 프레임
        """
        if df.empty or split_ratio <= 0.0 or split_ratio == 1.0:
            return df

        adjusted_df = df.copy()
        mask = adjusted_df.index < pd.to_datetime(event_date)

        for col in self.PRICE_COLUMNS:
            if col in adjusted_df.columns:
                adjusted_df.loc[mask, col] = adjusted_df.loc[mask, col] / split_ratio

        if self.VOLUME_COLUMN in adjusted_df.columns:
            adjusted_df.loc[mask, self.VOLUME_COLUMN] = adjusted_df.loc[mask, self.VOLUME_COLUMN] * split_ratio

        return adjusted_df

    def detect_abnormal_gap(self, prev_close: float, current_open: float) -> bool:
        """
        전일 종가 대비 당일 시가가 -30% 이상 하락 시 단순 폭락이 아닌 
        액면분할/배당락 이벤트일 확률이 높으므로 이를 감지합니다. (한국 증시 하한가 기준)
        
        Args:
            prev_close (float): 전일 종가
            current_open (float): 당일 시가
            
        Returns:
            bool: 비정상 갭락 발생 여부
        """
        if prev_close <= 0:
            return False
            
        drop_ratio = (current_open - prev_close) / prev_close
        return drop_ratio <= -0.30
