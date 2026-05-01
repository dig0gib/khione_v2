import asyncio
import logging
import pandas as pd
from app.core.kiwoom.market import kiwoom_market
from app.engine.signal_generator import signal_generator
from app.execution.auto_trader import auto_trader
from app.engine.state import global_state

# 로그 설정
logging.basicConfig(level=logging.INFO)

async def test_full_engine_loop():
    print("\n" + "="*50)
    print("Project Khione: Full Engine Integration Test")
    print("="*50)

    # 1. 엔진 활성화 (Kill-switch 해제)
    global_state.set_trading_active(True)
    print(f"[1] Trading Active: {global_state.is_trading_active}")

    # 2. 시장 데이터 수집 (삼성전자 005930)
    symbol = "005930"
    print(f"[2] Fetching market data for {symbol}...")
    price_data = await kiwoom_market.get_current_price(symbol)
    
    # 3. 데이터프레임 변환 (에이전트 분석용)
    # 실제로는 타임시리즈 데이터가 필요하지만, 테스트를 위해 현재가 기반 더미 생성
    cur_price = int(price_data.get("cur_prc", 0))
    print(f"    - Current Price: {cur_price}")
    
    df = pd.DataFrame([{
        "close": cur_price,
        "volume": int(price_data.get("trde_qty", 0)),
        "high": int(price_data.get("high_pric", 0)),
        "low": int(price_data.get("low_pric", 0)),
        "open": int(price_data.get("open_pric", 0))
    }])

    # 4. 신호 생성
    print("[3] Generating signals from agents...")
    # 테스트를 위해 에이전트의 강제 신호를 유도할 수 있으나, 현재는 기본 로직 실행
    # (ScalpingAgent가 score 0.5를 주므로 HOLD가 나올 것임)
    signal = signal_generator.generate_final_signal(symbol, df)
    print(f"    - Consensus Action: {signal['consensus_action']}")
    print(f"    - Regime: {signal['regime']}")

    # 5. 주문 실행 (테스트를 위해 강제로 BUY 신호 주입 가능)
    print("[4] Executing signal via AutoTrader...")
    # 강제 BUY 테스트
    test_signal = signal.copy()
    test_signal["consensus_action"] = "BUY"
    await auto_trader.execute_signal(symbol, test_signal)

    print("\n" + "="*50)
    print("Integration Test Completed")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(test_full_engine_loop())
