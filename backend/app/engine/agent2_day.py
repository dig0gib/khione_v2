import pandas as pd
from typing import Dict, Any
from app.engine.base_agent import BaseAgent

import numpy as np

class DummyPPOModel:
    """임시 PPO 모델: 실제 .pt 가중치 파일 연동 전까지 통계적 특성을 이용해 행동을 모의 생성합니다."""
    def predict(self, df: pd.DataFrame) -> tuple[int, float]:
        # 0: HOLD, 1: BUY, 2: SELL
        returns = df['close'].pct_change().dropna()
        if returns.empty:
            return 0, 0.0
            
        volatility = returns.std()
        momentum = returns.mean()
        
        confidence = float(np.clip(abs(momentum) / (volatility + 1e-6), 0.1, 0.9))
        
        if momentum > 0.005:  # 강한 상승 모멘텀
            return 1, confidence
        elif momentum < -0.005: # 강한 하락 모멘텀
            return 2, confidence
        return 0, confidence

class DayTradingAgent(BaseAgent):
    """
    Agent2: 일봉/수급 기반 데이트레이딩 에이전트.
    강화학습(PPO) 모델을 기반으로 일일 추세 및 수급을 분석하여 당일 청산을 목표로 신호를 생성합니다.
    """
    def __init__(self) -> None:
        super().__init__(agent_id="agent2_day")
        self.ppo_model = DummyPPOModel()

    async def analyze(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        일봉 데이터를 강화학습 모델에 입력하여 데이트레이딩 진입 신호를 도출합니다.
        """
        if market_data.empty:
            return {"score": 0.0, "confidence": 0.0, "action": "HOLD"}

        # PPO 모델 추론 로직 적용
        action_idx, confidence = self.ppo_model.predict(market_data)
        
        action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        action = action_map.get(action_idx, "HOLD")
        
        # PPO Action에 따른 Score 매핑
        score_map = {"BUY": 0.8, "SELL": 0.2, "HOLD": 0.5}
        score = score_map[action]

        return {
            "score": score,
            "confidence": confidence,
            "action": action,
            "agent": self.agent_id
        }
