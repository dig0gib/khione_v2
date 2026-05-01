import asyncio
import logging
import sys
import os

# 백엔드 디렉토리를 경로에 추가하여 app 모듈을 불러올 수 있게 함
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.kiwoom.auth import kiwoom_auth
from app.core.kiwoom.account import kiwoom_account
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_connection():
    print("\n" + "="*50)
    print("Project Khione: Kiwoom REST API Connection Test")
    print("="*50)
    
    print(f"\n[1] Check Settings")
    print(f"- Environment: {settings.ENVIRONMENT}")
    print(f"- App Key: {settings.KIWOOM_APP_KEY[:5]}***")
    print(f"- Account: {settings.KIWOOM_ACCOUNT_NUM}")
    
    # Check for empty or placeholder keys
    if not settings.KIWOOM_APP_KEY or "your_" in settings.KIWOOM_APP_KEY:
        print("\n[!] Error: KIWOOM_APP_KEY is not set or contains placeholder.")
        print("Please edit the .env file in the backend folder and enter your real keys.")
        return

    try:
        print(f"\n[2] Testing Access Token Issuance...")
        token = await kiwoom_auth.get_access_token()
        print(f"OK: Token issued successfully (Bearer {token[:10]}...)")
        
        print(f"\n[3] Testing Account Balance Inquiry...")
        try:
            balance = await kiwoom_account.get_balance()
            print(f"OK: API communication verified")
            print(f"- Response Summary: {str(balance)[:100]}...")
        except Exception as e:
            print(f"Warning: Token issued but data inquiry failed.")
            print(f"  (Check account number or domain settings: mock vs production)")
            print(f"  Error Detail: {e}")

    except Exception as e:
        print(f"\nError: API connection failed")
        print(f"Detail: {e}")

    print("\n" + "="*50)

if __name__ == "__main__":
    asyncio.run(test_connection())
