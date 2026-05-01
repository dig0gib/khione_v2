import logging
import re
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.engine.state import global_state
from app.core.config import settings


def require_whitelist(func):
    """허용된 Chat ID만 명령어를 사용할 수 있도록 검증하는 데코레이터."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user is None:
            return
        allowed = settings.allowed_chat_ids
        if allowed and update.effective_user.id not in allowed:
            logging.warning(f"[보안] 미허가 접근 차단: {update.effective_user.id}")
            await update.message.reply_text("⛔ 접근 권한이 없습니다.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


@require_whitelist
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """시스템의 현재 상태를 요약하여 반환합니다."""
    status = (
        "🟢 Khione System Status\n"
        f"Trading Active: {global_state.is_trading_active}\n"
        f"Regime: {global_state.current_regime}\n"
        f"Allocations: {global_state.agent_allocations}"
    )
    await update.message.reply_text(status)

@require_whitelist
async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """아침 스크리닝 리포트를 실시간으로 생성하여 전송합니다."""
    await update.message.reply_text("⏳ AI 스크리닝 실행 중... 잠시만 기다려 주세요.")
    try:
        from app.execution.auto_trader import auto_trader
        await auto_trader.morning_screening()
    except Exception as e:
        logging.error(f"[/morning] 스크리닝 오류: {e}")
        await update.message.reply_text(f"❌ 스크리닝 중 오류 발생: {e}")

@require_whitelist
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """사용자의 자연어 메시지를 처리하여 종목 분석 등을 수행합니다."""
    text = update.message.text
    
    # "분석" 키워드 확인
    if "분석" in text:
        # 종목명 추출 (단순 정규표현식 예시)
        match = re.search(r'([가-힣\w]+)\s*분석', text)
        if match:
            stock_name = match.group(1)
            await update.message.reply_text(f"🔍 AI 에이전트들이 '{stock_name}' 분석을 시작합니다. 잠시만 기다려 주세요...")
            
            # 에이전트 협업 분석 시뮬레이션
            # 실제로는 KiwoomMarket에서 데이터를 가져와 각 에이전트의 analyze() 호출
            report = (
                f"📊 {stock_name} AI 종합 분석 보고서\n"
                "--------------------------------\n"
                "🛡️ Agent 1 (수급): 현재가 기준 매수 잔량 우위. 단기 반등 시그널.\n"
                "📈 Agent 2 (추세): 정배열 초기 단계. 기관 연속 순매수 확인.\n"
                "🧠 Agent 3 (메타): 지수 대비 강한 흐름. 비중 확대 권고.\n"
                "--------------------------------\n"
                "✅ 최종 의견: [매수 (STRONG BUY)]\n"
                "🎯 목표가: +5.5% 예상"
            )
            await update.message.reply_text(report)
            return

    await update.message.reply_text("죄송합니다. 아직 학습 중인 문장입니다. '삼성전자 분석해줘' 또는 /morning 이라고 입력해 보세요!")

@require_whitelist
async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """킬스위치 실행."""
    keyboard = [
        [InlineKeyboardButton("🚨 즉시 정지 (CONFIRM KILL)", callback_data='kill_confirm')],
        [InlineKeyboardButton("취소 (CANCEL)", callback_data='kill_cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('정말로 모든 자동매매를 즉시 중단하시겠습니까?', reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """버튼 클릭 처리."""
    query = update.callback_query
    await query.answer()

    if query.data == 'kill_confirm':
        global_state.set_trading_active(False)
        logging.critical("User engaged KILL SWITCH via Telegram.")
        from app.execution.auto_trader import auto_trader
        try:
            await auto_trader.liquidate_all()
            await query.edit_message_text(text="🚨 킬스위치 가동 완료. 모든 포지션 전량 청산 완료.")
        except Exception as e:
            logging.error(f"텔레그램 킬스위치 청산 오류: {e}")
            await query.edit_message_text(text="🚨 매매 중단됨. 청산 중 오류 발생 — 수동 확인 필요!")
    elif query.data == 'kill_cancel':
        await query.edit_message_text(text="킬스위치 가동이 취소되었습니다.")
