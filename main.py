import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Пути к файлам
COMMENTS_FILE = Path("data/comments.json")
STATIC_DIR = Path("static")
DATA_DIR = Path("data")

# Модели данных
class CommentCreate(BaseModel):
    author: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=1000)

class Comment(BaseModel):
    id: int
    author: str
    text: str
    created_at: str

# Вспомогательные функции
def load_comments() -> List[dict]:
    """Загрузка комментариев из JSON файла"""
    try:
        if COMMENTS_FILE.exists():
            with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
                comments = json.load(f)
                logger.info(f"Загружено {len(comments)} комментариев")
                return comments
        logger.info("Файл комментариев не найден, создается новый")
        return []
    except Exception as e:
        logger.error(f"Ошибка при загрузке комментариев: {e}")
        return []

def save_comments(comments: List[dict]) -> bool:
    """Сохранение комментариев в JSON файл"""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(comments, f, ensure_ascii=False, indent=2)
        logger.info(f"Сохранено {len(comments)} комментариев")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении комментариев: {e}")
        return False

# Lifespan для инициализации
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создание необходимых директорий
    DATA_DIR.mkdir(exist_ok=True)
    STATIC_DIR.mkdir(exist_ok=True)
    logger.info("Приложение запущено")
    yield
    logger.info("Приложение остановлено")

# Создание приложения
app = FastAPI(
    title="lil_vludick Personal Page",
    description="Персональная страница с гостевой книгой",
    version="1.0.0",
    lifespan=lifespan
)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Запрос: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"Ответ: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        raise

# Маршруты
@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Главная страница"""
    try:
        html_path = Path("static/index.html")
        if not html_path.exists():
            logger.error("index.html не найден")
            raise HTTPException(status_code=404, detail="Страница не найдена")
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info("Главная страница отправлена")
        return HTMLResponse(content=content)
    except Exception as e:
        logger.error(f"Ошибка при загрузке главной страницы: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/api/comments", response_model=List[Comment])
async def get_comments():
    """Получение всех комментариев"""
    try:
        comments = load_comments()
        # Сортировка от новых к старым
        comments.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        logger.info(f"Запрошены комментарии: {len(comments)} шт.")
        return comments
    except Exception as e:
        logger.error(f"Ошибка при получении комментариев: {e}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки комментариев")

@app.post("/api/comments", response_model=Comment)
async def create_comment(comment: CommentCreate):
    """Создание нового комментария"""
    try:
        comments = load_comments()
        
        # Генерация ID
        new_id = max([c.get('id', 0) for c in comments], default=0) + 1
        
        # Создание нового комментария
        new_comment = {
            "id": new_id,
            "author": comment.author.strip(),
            "text": comment.text.strip(),
            "created_at": datetime.now().isoformat()
        }
        
        comments.append(new_comment)
        
        if not save_comments(comments):
            raise HTTPException(status_code=500, detail="Ошибка сохранения комментария")
        
        logger.info(f"Создан комментарий #{new_id} от {new_comment['author']}")
        return new_comment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при создании комментария: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания комментария")

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )