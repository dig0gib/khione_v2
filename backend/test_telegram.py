import httpx
import asyncio
import os
from app.core.config import settings

async def send_test_message():
    token = settings.TELEGRAM_BOT_TOKEN
    # 첫 번째 허용된 ID를 대상으로 전송
    chat_id = settings.TELEGRAM_ALLOWED_CHAT_IDS.split(",")[0].strip()
    
    if not token or not chat_id:
        print("Error: Token or Chat ID is missing.")
        return

    text = (
        "🚀 Khione System Integration Test\n\n"
        "텔레그램 봇 연동이 성공적으로 완료되었습니다!\n"
        "아래 명령어를 사용하여 시스템을 제어할 수 있습니다:\n\n"
        "1. /status : 실시간 엔진 상태 보고\n"
        "2. /kill : 비상 정지 및 전량 청산\n\n"
        "현재 시스템은 자율 매매 준비 상태(NORMAL)입니다."
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print("SUCCESS: Telegram message sent successfully!")
            else:
                print(f"FAILED: {response.text}")
        except Exception as e:
            print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(send_test_message())
