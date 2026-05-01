import logging
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import InvalidToken
from app.telegram_bot.handlers import cmd_status, cmd_kill, cmd_morning, handle_message, button_callback
from app.core.config import settings


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(f"[텔레그램 봇] 예외 발생: {context.error}", exc_info=context.error)


def build_telegram_bot() -> Optional[Application]:
    """
    텔레그램 봇 애플리케이션을 빌드합니다. 
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or ":" not in token:
        logging.warning("유효한 TELEGRAM_BOT_TOKEN이 설정되지 않았습니다. 텔레그램 봇 기능을 제외하고 시작합니다.")
        return None
        
    try:
        application = Application.builder().token(token).build()
        
        # 명령어 등록
        application.add_handler(CommandHandler("status", cmd_status))
        application.add_handler(CommandHandler("kill", cmd_kill))
        application.add_handler(CommandHandler("morning", cmd_morning))
        application.add_handler(CommandHandler("screen", cmd_morning))
        
        # 자연어 메시지 처리 등록
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # 인라인 버튼 콜백 등록
        application.add_handler(CallbackQueryHandler(button_callback))

        # 전역 에러 핸들러
        application.add_error_handler(_error_handler)

        return application
    except InvalidToken:
        logging.error("제공된 텔레그램 토큰이 유효하지 않습니다. 봇 기능을 비활성화합니다.")
        return None
