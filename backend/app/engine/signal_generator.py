import pandas as pd
from typing import Dict, Any
from app.engine.agent1_scalping import ScalpingAgent
from app.engine.agent2_day import DayTradingAgent
from app.engine.agent3_meta import MetaAgent
from app.engine.state import global_state

class SignalGenerator:
    """
    신호 합성기 (Signal Synthesizer).
    3개의 독립된 에이전트(Agent1, Agent2, Agent3)의 분석 결과를 취합하여
    글로벌 상태(SystemState)를 업데이트하고, 최종 실행 가능한 매매 신호를 도출합니다.
    """
    def __init__(self) -> None:
        self.agent1 = ScalpingAgent()
        self.agent2 = DayTradingAgent()
        self.agent3 = MetaAgent()

    async def generate_final_signal(self, symbol: str, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        각 에이전트의 개별 신호를 종합하여 최종 합의(Consensus) 액션을 결정합니다.
        
        Args:
            symbol (str): 분석 대상 종목코드
            market_data (pd.DataFrame): 해당 종목의 시장 데이터
            
        Returns:
            Dict[str, Any]: 최종 매수/매도/관망 신호 및 모든 메타데이터
        """
        # 1. 메타 에이전트(Agent3)를 통한 레짐 분석 및 비중 조절
        meta_result = await self.agent3.analyze(market_data)
        global_state.current_regime = meta_result.get("regime", "UNKNOWN")
        global_state.update_allocation(meta_result.get("allocation", {}))

        # 2. 실행 에이전트(Agent1, Agent2) 신호 도출
        a1_result = await self.agent1.analyze(market_data)
        a2_result = await self.agent2.analyze(market_data)

        # 3. 합의 로직 (Consensus Logic)
        # 킬스위치가 발동되었거나, 거래가 중지된 상태라면 무조건 관망
        if not global_state.is_trading_active:
            consensus = "HOLD"
        else:
            # Agent3(메타)의 레짐 판단을 포함한 3/3 투표 기반 합의
            # BEAR 레짐에서는 BUY 신호 차단 (방어 로직)
            regime = global_state.current_regime
            a3_action = meta_result.get("action", "HOLD")

            votes_buy  = sum(1 for a in [a1_result, a2_result, meta_result] if a.get("action") == "BUY")
            votes_sell = sum(1 for a in [a1_result, a2_result, meta_result] if a.get("action") == "SELL")

            if votes_buy >= 2 and regime != "BEAR":
                consensus = "BUY"
            elif votes_sell >= 2:
                consensus = "SELL"
            else:
                consensus = "HOLD"

        final_signal = {
            "symbol": symbol,
            "timestamp": pd.Timestamp.now().isoformat(),
            "consensus_action": consensus,
            "regime": global_state.current_regime,
            "agent_signals": {
                "agent1": a1_result,
                "agent2": a2_result,
                "agent3": meta_result
            }
        }
        
        return final_signal

# 전역 싱글톤 인스턴스
signal_generator = SignalGenerator()
