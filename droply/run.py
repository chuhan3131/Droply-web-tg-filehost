import asyncio
import threading
import uvicorn
from api.main import app as api_app
from bot.main import main as bot_main
from bot.config import HOST, PORT

def run_api():
    uvicorn.run(api_app, host=HOST, port=PORT, log_level="info")

def run_bot():
    asyncio.run(bot_main())

if __name__ == "__main__":
    print(f"Запуск Droply на {HOST}:{PORT}")
    print("Telegram бот запускается...")
    print("Веб-интерфейс запускается...")
    
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nDroply остановлен")
    except Exception as e:
        print(f"\nОшибка: {e}")