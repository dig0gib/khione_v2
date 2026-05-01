import logging
from typing import List
from telegram import Bot
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_telegram_notification(message: str):
    """
    설정된 모든 TELEGRAM_ALLOWED_CHAT_IDS 사용자에게 메시지를 발송합니다.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_ids = settings.allowed_chat_ids

    if not token or not chat_ids:
        logger.warning("텔레그램 알림을 보낼 수 없습니다. 토큰 또는 Chat ID가 설정되지 않았습니다.")
        return

    async with Bot(token) as bot:
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
                logger.info(f"✅ 텔레그램 알림 발송 성공 (Chat ID: {chat_id})")
            except Exception as e:
                logger.error(f"❌ 텔레그램 알림 발송 실패 (Chat ID: {chat_id}): {str(e)}")
