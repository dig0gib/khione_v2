from pydantic import BaseModel, Field
from typing import Dict, Any, List

class SystemState(BaseModel):
    """
    시스템 전역 상태 관리 엔진 (Single Source of Truth)
    웹 대시보드, 텔레그램 봇, 트레이딩 엔진 간의 상태 동기화를 담당합니다.
    """
    is_trading_active: bool = Field(default=False, description="자동 매매 실행 여부")
    current_regime: str = Field(default="NORMAL", description="현재 시장 레짐 (예: BULL, BEAR, VOLATILE)")
    agent_allocations: Dict[str, float] = Field(
        default={"agent1_scalping": 0.0, "agent2_day": 0.0, "agent3_meta": 0.0},
        description="에이전트별 자산 배분 비율"
    )
    active_positions: Dict[str, Any] = Field(default_factory=dict, description="현재 보유 중인 포지션 목록 {symbol: {qty, avg_price, ...}}")
    today_watch_list: Dict[str, str] = Field(default_factory=dict, description="당일 스크리닝 확정 종목 {symbol: name}. 매일 08:30 갱신.")
    decision_stream: List[Any] = Field(default_factory=list, description="최근 의사결정 기록 (최대 20건)")
    macro_data: Dict[str, Any] = Field(
        default_factory=lambda: {"base_rate": 0.0, "usd_krw": 0.0, "dart_summary": ""},
        description="거시지표 캐시 (DART 공시, 한국은행 금리/환율) - 08:30 수집"
    )


    def update_allocation(self, allocations: Dict[str, float]) -> None:
        """Agent3(메타 에이전트)에 의해 결정된 자산 배분 비율을 업데이트합니다."""
        self.agent_allocations = allocations

    def set_trading_active(self, status: bool) -> None:
        """킬스위치(Kill-Switch) 또는 재시작 시 상태를 변경합니다."""
        self.is_trading_active = status

# 전역 싱글톤 상태 객체
global_state = SystemState()
