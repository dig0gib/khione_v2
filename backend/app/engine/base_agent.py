from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any

class BaseAgent(ABC):
    """
    모든 트레이딩 에이전트의 추상 기본 클래스 (Abstract Base Class).
    객체지향의 개방-폐쇄 원칙(OCP)을 준수하여 새로운 전략 에이전트 추가를 용이하게 합니다.
    """
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abstractmethod
    async def analyze(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        시장 데이터를 분석하여 매매 신호 및 스코어를 산출합니다.
        
        Args:
            market_data (pd.DataFrame): 분석 대상 시장 데이터 (수정주가 보정 완료)
            
        Returns:
            Dict[str, Any]: 에이전트의 분석 결과 (신호, 확신도 등)
        """
        pass
