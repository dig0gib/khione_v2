import logging
from typing import Dict, Any
from app.core.kiwoom.client import kiwoom_client
from app.core.config import settings

class KiwoomOrder:
    """
    키움증권 REST API 주문 실행 모듈 (매수, 매도, 취소, 비상 정지)
    """
    def __init__(self):
        self.client = kiwoom_client
        self.account_num = settings.KIWOOM_ACCOUNT_NUM

    async def send_order(self, symbol: str, order_type: str, qty: int, price: int = 0) -> Dict[str, Any]:
        """
        주식 주문 전송 (kt10000: 매수, kt10001: 매도)
        order_type: "0" (보통/지정가), "3" (시장가)
        """
        logging.info(f"[{symbol}] 주문 실행 요청 (수량: {qty}, 가격: {price})")
        
        # 가이드 명세에 따른 페이로드 구성
        payload = {
            "dmst_stex_tp": "KRX", # 국내거래소구분
            "stk_cd": symbol,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price > 0 else "",
            "trde_tp": order_type, # 0:보통, 3:시장가
            "cond_uv": ""
        }
        
        # TR ID 결정 (매수/매도 구분은 외부에서 tr_id를 넘기거나 로직 분리 필요)
        # 여기서는 편의상 order_type에 따라 유추하거나, 파라미터를 확장하여 처리
        # 일단 매수(kt10000)를 기본으로 예시 작성
        api_id = "kt10000" if int(order_type) in [0, 3] else "kt10001" 

        # Priority 1 (주문 실행)
        result = await self.client.execute(
            priority=1,
            method="POST",
            path="/api/dostk/ordr",
            api_id=api_id,
            payload=payload
        )
        return result

    async def cancel_order(self, org_order_no: str, symbol: str, qty: int) -> Dict[str, Any]:
        """
        주식 취소 주문 (kt10003)
        """
        logging.info(f"[{symbol}] 원주문번호 {org_order_no} 취소 요청...")
        
        payload = {
            "dmst_stex_tp": "KRX",
            "org_ord_no": org_order_no, # 가이드 필드명 확인 필요 (보통 org_ord_no)
            "stk_cd": symbol,
            "ord_qty": str(qty),
            "trde_tp": "0" # 취소 시 기본값
        }
        
        # Priority 0 (주문 취소)
        result = await self.client.execute(
            priority=0,
            method="POST",
            path="/api/dostk/ordr",
            api_id="kt10003",
            payload=payload
        )
        return result

    async def buy(self, symbol: str, qty: int, order_type: str = "3", price: int = 0) -> Dict[str, Any]:
        """주식 매수 (kt10000)"""
        return await self.send_order(symbol, order_type, qty, price)

    async def sell(self, symbol: str, qty: int, order_type: str = "3", price: int = 0) -> Dict[str, Any]:
        """주식 매도 (kt10001)"""
        # send_order 로직에서 order_type이 0, 3이 아니면 kt10001을 타도록 되어 있음
        # 하지만 가이드상 매도(kt10001) 시 trde_tp는 매수와 동일하게 0(보통), 3(시장가) 등을 사용함
        # 따라서 send_order 내부의 api_id 결정 로직을 수정해야 함
        return await self.send_order_v2(symbol, "kt10001", order_type, qty, price)

    async def send_order_v2(self, symbol: str, api_id: str, order_type: str, qty: int, price: int = 0, exchange: str = "KRX") -> Dict[str, Any]:
        """공통 주문 실행 (v2: api_id 및 거래소 명시)"""
        # 종목코드 접미사 처리 (NXT: _NX, SOR: _AL)
        formatted_symbol = symbol
        if exchange == "NXT" and not symbol.endswith("_NX"):
            formatted_symbol = f"{symbol}_NX"
        elif exchange == "SOR" and not symbol.endswith("_AL"):
            formatted_symbol = f"{symbol}_AL"

        logging.info(f"[{formatted_symbol}] {exchange} {api_id} 주문 요청 (수량: {qty}, 가격: {price})")
        
        payload = {
            "dmst_stex_tp": exchange, # KRX, NXT, SOR
            "stk_cd": formatted_symbol,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price > 0 else "",
            "trde_tp": order_type, # 0:보통, 3:시장가
            "cond_uv": ""
        }
        return await self.client.execute(1, "POST", "/api/dostk/ordr", api_id, payload)

    async def check_risk_and_order(self, symbol: str, api_id: str, qty: int, price: int = 0, exchange: str = "KRX"):
        """리스크 관리 로직이 포함된 안전 주문 함수"""
        # 1. 주문 인출 가능 금액 확인 (kt00010)
        from app.core.kiwoom.account import kiwoom_account
        cash_data = await kiwoom_account.get_withdrawable_amount()
        # 가이드상 ord_psbl_amt (주문가능금액) 필드 확인 필요
        withdrawable = int(cash_data.get("ord_psbl_amt", 0))
        
        # 2. 예상 주문 금액 계산
        order_amount = qty * (price if price > 0 else 0) # 시장가는 0으로 처리되나 실제론 현재가 기준 체크 필요
        
        if order_amount > withdrawable:
            logging.error(f"🚨 잔고 부족으로 주문이 거부되었습니다. (가능액: {withdrawable}, 필요액: {order_amount})")
            return {"error": "INSUFFICIENT_FUNDS"}
            
        # 3. 주문 실행
        return await self.send_order_v2(symbol, api_id, "3" if price == 0 else "0", qty, price, exchange)

    async def emergency_kill_switch(self, open_positions: list):
        """
        Black Swan (돌발 변수) 발생 시 호출되는 전량 시장가 청산 로직
        """
        logging.critical("🚨 비상 정지(Kill-Switch) 가동! 모든 보유 잔고를 시장가로 즉시 매도합니다.")
        results = []
        for pos in open_positions:
            symbol = pos.get("symbol")
            qty = pos.get("qty")
            if symbol and qty > 0:
                # "3" = 시장가 매도
                res = await self.sell(symbol=symbol, qty=qty, order_type="3")
                results.append(res)
        return results

kiwoom_order = KiwoomOrder()
