import logging
from typing import Dict, Any, List
from app.core.kiwoom.client import kiwoom_client
from app.core.config import settings

class KiwoomAccount:
    """
    키움증권 REST API 계좌 정보 조회 모듈 (25개 이상의 모든 TR 연동)
    """
    def __init__(self):
        self.client = kiwoom_client
        self.account_num = settings.KIWOOM_ACCOUNT_NUM

    async def _execute_acnt_tr(self, api_id: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """계좌 관련 TR 공통 실행 메서드"""
        if payload is None:
            payload = {}
        return await self.client.execute(
            priority=2,
            method="POST",
            path="/api/dostk/acnt",
            api_id=api_id,
            payload=payload
        )

    # --- [계좌 기본 및 예수금] ---
    async def get_account_list(self):
        """ka00001: 계좌번호조회"""
        return await self._execute_acnt_tr("ka00001")

    async def get_deposit_detail(self):
        """kt00001: 예수금상세현황요청"""
        return await self._execute_acnt_tr("kt00001")

    async def get_estimated_assets_daily(self):
        """kt00002: 일별추정예탁자산현황요청"""
        return await self._execute_acnt_tr("kt00002")

    async def get_estimated_assets(self):
        """kt00003: 추정자산조회요청"""
        return await self._execute_acnt_tr("kt00003")

    async def get_account_evaluation(self):
        """kt00004: 계좌평가현황요청"""
        return await self._execute_acnt_tr("kt00004")

    # --- [손익 및 수익률] ---
    async def get_daily_profit_rate(self):
        """ka01690: 일별잔고수익률"""
        return await self._execute_acnt_tr("ka01690")

    async def get_profit_loss_by_date(self, date: str):
        """ka10072: 일자별종목별실현손익요청_일자"""
        return await self._execute_acnt_tr("ka10072", {"date": date})

    async def get_profit_loss_by_period(self, start_date: str, end_date: str):
        """ka10073: 일자별종목별실현손익요청_기간"""
        return await self._execute_acnt_tr("ka10073", {"sdate": start_date, "edate": end_date})

    async def get_daily_profit_loss(self):
        """ka10074: 일자별실현손익요청"""
        return await self._execute_acnt_tr("ka10074")

    async def get_daily_profit_loss_detail(self):
        """ka10077: 당일실현손익상세"""
        return await self._execute_acnt_tr("ka10077")

    async def get_account_yield(self):
        """ka10085: 계좌수익률요청"""
        return await self._execute_acnt_tr("ka10085")

    async def get_daily_yield_detail(self):
        """kt00016: 일별계좌수익률상세현황요청"""
        return await self._execute_acnt_tr("kt00016")

    # --- [주문 및 체결] ---
    async def get_unexecuted_orders(self):
        """ka10075: 미체결요청"""
        return await self._execute_acnt_tr("ka10075")

    async def get_executions(self):
        """ka10076: 체결요청"""
        return await self._execute_acnt_tr("ka10076")

    async def get_execution_balance(self):
        """kt00005: 체결잔고요청"""
        return await self._execute_acnt_tr("kt00005")

    async def get_order_execution_detail(self):
        """kt00007: 계좌별주문체결내역상세"""
        return await self._execute_acnt_tr("kt00007")

    async def get_order_execution_status(self):
        """kt00009: 계좌별주문체결현황요청"""
        return await self._execute_acnt_tr("kt00009")

    async def get_split_order_detail(self):
        """ka10088: 미체결 분할주문 상세"""
        return await self._execute_acnt_tr("ka10088")

    async def get_daily_trade_log(self):
        """ka10170: 당일매매일지요청"""
        return await self._execute_acnt_tr("ka10170")

    # --- [기타 자산 정보] ---
    async def get_withdrawable_amount(self):
        """kt00010: 주문인출가능금액요청"""
        return await self._execute_acnt_tr("kt00010")

    async def get_orderable_quantity_by_margin(self, margin_rate: str):
        """kt00011: 증거금율별주문가능수량조회요청"""
        return await self._execute_acnt_tr("kt00011", {"mgn_rate": margin_rate})

    async def get_margin_detail(self):
        """kt00013: 증거금세부내역조회요청"""
        return await self._execute_acnt_tr("kt00013")

    async def get_comprehensive_trade_history(self):
        """kt00015: 위탁종합거래내역요청"""
        return await self._execute_acnt_tr("kt00015")

    async def get_next_day_settlement(self):
        """kt00008: 계좌별익일결제예정내역요청"""
        return await self._execute_acnt_tr("kt00008")

kiwoom_account = KiwoomAccount()
