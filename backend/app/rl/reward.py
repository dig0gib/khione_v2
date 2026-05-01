import numpy as np
from typing import List

class RewardCalculator:
    """
    강화학습 보상(Reward) 계산기.
    단순 수익률이 아닌 하방 리스크를 억제하기 위해 Sortino Ratio 및 
    시장 대비 초과 수익(Alpha)을 보상 함수로 사용합니다.
    """
    
    @staticmethod
    def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        수익률 배열에 대한 Sortino Ratio를 계산합니다.
        
        Args:
            returns (List[float]): 수익률 목록
            risk_free_rate (float): 무위험 이자율
            
        Returns:
            float: Sortino Ratio
        """
        if not returns:
            return 0.0
            
        returns_array = np.array(returns)
        downside_returns = returns_array[returns_array < 0]
        expected_return = np.mean(returns_array) - risk_free_rate
        
        if len(downside_returns) == 0:
            return float('inf') # 하방 리스크가 없는 완벽한 경우
            
        downside_deviation = np.std(downside_returns)
        if downside_deviation == 0:
            return float('inf')
            
        return float(expected_return / downside_deviation)

    @staticmethod
    def compute_trade_reward(pnl_pct: float, benchmark_pct: float) -> float:
        """
        시장(벤치마크) 수익률 대비 초과 수익(Alpha)을 기반으로 개별 거래의 보상을 계산합니다.
        
        Args:
            pnl_pct (float): 실제 포지션 수익률
            benchmark_pct (float): 동기간 시장 인덱스(예: 코스피) 수익률
            
        Returns:
            float: 계산된 보상값
        """
        alpha = pnl_pct - benchmark_pct
        return alpha
