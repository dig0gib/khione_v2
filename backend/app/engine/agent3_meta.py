import pandas as pd
import logging
from typing import Dict, Any
from app.engine.base_agent import BaseAgent
from app.data.external_api import external_data_manager

class MetaAgent(BaseAgent):
    """
    Agent3: 시장 레짐 분석 및 자산 배분(비중 조절) 에이전트.
    거시적 시장 상태(Regime)를 파악하고 과거 실적을 바탕으로 Agent1, Agent2, 스윙 트레이딩 간의 자산 비중을 동적으로 배분합니다.
    """
    def __init__(self) -> None:
        super().__init__(agent_id="agent3_meta")

    async def analyze(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        이동평균선 및 외부 거시 경제 지표(기준금리 등)를 종합하여 레짐 판별 및 자산 배분.
        """
        if market_data.empty or len(market_data) < 20:
            return {
                "regime": "UNKNOWN",
                "allocation": {"agent1_scalping": 0.3, "agent2_day": 0.3, "swing": 0.4},
                "confidence": 0.0
            }

        # 1. 외부 거시 경제 지표 조회 (ECOS 기준금리)
        base_rate = await external_data_manager.get_base_rate()
        
        # 2. 지수(Index) 기반 레짐 판별
        close = market_data['close']
        ma20 = close.rolling(window=20).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        # 간단한 레짐 판별 로직 + 거시 경제 데이터 연동
        # 기준금리가 비정상적으로 높거나 급등한 상황이라고 가정 (예: 4.5% 이상)하면 보수적으로 접근
        is_high_interest = base_rate >= 4.5
        
        if is_high_interest:
            regime = "BEAR (HIGH INTEREST)"
            allocation = {"agent1_scalping": 0.1, "agent2_day": 0.1, "swing": 0.8} # 현금/안전 비중 확대
            logging.info(f"[{self.agent_id}] 고금리 레짐 감지! (기준금리: {base_rate}%)")
        elif current_price > ma20 * 1.05:
            regime = "BULL (OVERHEATED)"
            allocation = {"agent1_scalping": 0.2, "agent2_day": 0.4, "swing": 0.4}
        elif current_price > ma20:
            regime = "BULL"
            allocation = {"agent1_scalping": 0.5, "agent2_day": 0.3, "swing": 0.2}
        elif current_price < ma20 * 0.95:
            regime = "BEAR (CRASH)"
            allocation = {"agent1_scalping": 0.1, "agent2_day": 0.1, "swing": 0.8} # 현금 비중 확대
        else:
            regime = "NORMAL"
            allocation = {"agent1_scalping": 0.4, "agent2_day": 0.4, "swing": 0.2}

        return {
            "regime": regime,
            "allocation": allocation,
            "confidence": 0.9,
            "agent": self.agent_id,
            "macro_data": {"base_rate": base_rate}
        }
