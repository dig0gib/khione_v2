"""
신호 합성기 (Signal Synthesizer) — V2
- Agent1: Agent1Scalping (호가창 역설 + 체결강도 기반)
- Agent2: DayTradingAgent (DummyPPO 기반, 향후 실제 PPO 교체)
- Agent3: MetaAgent (레짐 판별 + 거시지표 캐시 연동)
"""
import pandas as pd
from typing import Dict, Any
from app.engine.agent1_scalping import Agent1Scalping
from app.engine.agent2_day import DayTradingAgent
from app.engine.agent3_meta import MetaAgent
from app.engine.state import global_state


class SignalGenerator:
    """
    3개의 독립된 에이전트의 분석 결과를 취합하여
    글로벌 상태를 업데이트하고, 최종 실행 가능한 매매 신호를 도출합니다.
    """
    def __init__(self) -> None:
        self.agent1 = Agent1Scalping()
        self.agent2 = DayTradingAgent()
        self.agent3 = MetaAgent()

    async def generate_final_signal(self, symbol: str, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        각 에이전트의 개별 신호를 종합하여 최종 합의(Consensus) 액션을 결정합니다.
        """
        # 1. 메타 에이전트(Agent3)를 통한 레짐 분석 및 비중 조절
        meta_result = await self.agent3.analyze(market_data)
        global_state.current_regime = meta_result.get("regime", "UNKNOWN")
        global_state.update_allocation(meta_result.get("allocation", {}))

        # 2. 실행 에이전트(Agent1, Agent2) 신호 도출
        a1_result = await self.agent1.analyze(market_data)
        a2_result = await self.agent2.analyze(market_data)

        # 3. 합의 로직 (Consensus Logic)
        if not global_state.is_trading_active:
            consensus = "HOLD"
        else:
            regime = global_state.current_regime
            votes_buy = sum(1 for a in [a1_result, a2_result, meta_result] if a.get("action") == "BUY")
            votes_sell = sum(1 for a in [a1_result, a2_result, meta_result] if a.get("action") == "SELL")

            if votes_buy >= 2 and "BEAR" not in regime:
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
