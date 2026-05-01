from typing import Dict, Any, List

class ReplayMemory:
    """
    강화학습 리플레이 버퍼 (Replay Memory).
    매매일지 데이터를 (State, Action, Reward, Next_State) 튜플 형태로 변환 및 보관합니다.
    """
    def __init__(self, capacity: int = 10000) -> None:
        self.capacity = capacity
        self.buffer: List[Dict[str, Any]] = []

    def add_experience(self, state: Dict[str, Any], action: str, reward: float, next_state: Dict[str, Any]) -> None:
        """
        새로운 경험(Experience Tuple)을 버퍼에 추가합니다.
        용량이 초과되면 가장 오래된 데이터를 삭제합니다.
        """
        if len(self.buffer) >= self.capacity:
            self.buffer.pop(0)
            
        self.buffer.append({
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state
        })

    def negative_sampling(self, rejected_candidates: List[Dict[str, Any]]) -> None:
        """
        스크리닝에서 탈락한 종목(Negative Samples)도 학습 데이터에 추가하여
        RL 모델이 '매수하지 말아야 할 때'를 학습하도록 돕습니다.
        
        Args:
            rejected_candidates (List[Dict[str, Any]]): 진입하지 않은 종목 상태 리스트
        """
        for candidate in rejected_candidates:
            # 탈락한 종목의 행동은 'HOLD', 보상은 0.0 (또는 기회비용 패널티)로 설정
            self.add_experience(
                state=candidate.get("state", {}),
                action="HOLD",
                reward=0.0,
                next_state=candidate.get("next_state", {})
            )
