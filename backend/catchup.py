import asyncio
import logging
from app.scheduler.tasks import morning_screening_task, start_trading_task
from app.data.database import init_db

logging.basicConfig(level=logging.INFO)

async def main():
    print("Running catch-up tasks for 08:30 and 09:00...")
    await init_db()
    await morning_screening_task()
    await start_trading_task()
    print("Catch-up complete. Trading is now ACTIVE.")

if __name__ == "__main__":
    asyncio.run(main())
