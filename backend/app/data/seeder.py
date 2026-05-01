import logging
import pandas as pd
from typing import Optional, Any
from pathlib import Path
from app.data.adjuster import PriceAdjuster

class DataSeeder:
    """
    과거 시계열 데이터(10년 치 일봉 등)를 수집하고 PriceAdjuster로 보정하여 
    강화학습 및 백테스팅을 위한 Parquet 포맷으로 로컬 스토리지에 고속 적재합니다.
    """
    
    def __init__(self, market_client: Any, data_dir: str = "data/history"):
        """
        Args:
            market_client: KiwoomMarket 인스턴스 (의존성 주입)
            data_dir: 시계열 데이터 저장 경로
        """
        self.market = market_client
        self.adjuster = PriceAdjuster()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def seed_historical_daily(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        특정 종목의 과거 일봉 데이터를 수집하고 보정 후 Parquet 파일로 저장합니다.
        
        Args:
            symbol (str): 종목코드
            start_date (str): 조회 시작일 (YYYYMMDD)
            end_date (str): 조회 종료일 (YYYYMMDD)
            
        Returns:
            Optional[pd.DataFrame]: 수집 성공 시 데이터프레임 반환, 실패 시 None
        """
        logging.info(f"[{symbol}] 과거 일봉 시딩 시작 ({start_date} ~ {end_date})")
        
        try:
            response = await self.market.get_daily_chart(
                symbol=symbol, 
                start_date=start_date, 
                end_date=end_date
            )
            
            items = response.get("output", [])
            if not items:
                logging.warning(f"[{symbol}] 반환된 데이터가 없습니다.")
                return None
                
            df = pd.DataFrame(items)
            
            # API 응답 필드명 -> 통일된 포맷 매핑
            col_map = {
                "stck_bsop_date": "date",
                "stck_oprc": "open",
                "stck_hgpr": "high",
                "stck_lwpr": "low",
                "stck_clpr": "close",
                "acml_vol": "volume"
            }
            actual_col_map = {k: v for k, v in col_map.items() if k in df.columns}
            df.rename(columns=actual_col_map, inplace=True)
            
            # 인덱스 설정 및 타입 변환
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 강화학습 파이프라인의 입출력 속도를 극대화하기 위해 Parquet 포맷 활용
            file_path = self.data_dir / f"{symbol}_daily.parquet"
            df.to_parquet(file_path, engine="pyarrow")
            
            logging.info(f"[{symbol}] 총 {len(df)}건의 데이터 수집 및 {file_path} 적재 완료.")
            return df
            
        except Exception as e:
            logging.error(f"[{symbol}] 시딩 중 에러 발생: {e}")
            return None
