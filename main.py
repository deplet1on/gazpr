from fastapi import FastAPI, HTTPException, Query, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import and_, create_engine, Column, Integer, String, Float, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import csv
import io
import re
import logging
from datetime import datetime
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.dialects.postgresql import insert
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from fastapi import Body
from fastapi import WebSocket
from fastapi_cache.decorator import cache
from contextlib import asynccontextmanager
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Set
from fastapi.websockets import WebSocket

alert_connections: Set[WebSocket] = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация при старте
    print("App started")
    yield
    # Очистка при завершении
    print("Closing connections")
    for connection in alert_connections:
        await connection.close()
    alert_connections.clear()

app = FastAPI(lifespan=lifespan)

@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")

# Инициализация
Base = declarative_base()
load_dotenv()



DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, connect_args={"client_encoding": "UTF8"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка логов
logging.basicConfig(filename='api_errors.log', level=logging.ERROR)

# Модель Pydantic
class SensorDataResponse(BaseModel):
    timestamp: datetime
    pipe_number: str
    sensor_type: str
    sensor_number: int
    value: float
    sensor_id: str  # Добавлено поле

class AlertRequest(BaseModel):
    sensor_id: Optional[str] 
    start_date: Optional[datetime] 
    end_date: Optional[datetime] 

class Config:
    orm_mode = True
# Pydantic модель для ответа
class ExtremesResponse(BaseModel):
    min: Optional[float]
    max: Optional[float]
class AlertResponse(BaseModel):
    alert: bool
    message: Optional[str]
    current_avg: Optional[float]
    threshold: float

class UploadResponse(BaseModel):
    message: str
    new_records: int
    duplicates: int
    alert: Optional[AlertResponse]

class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int

# Модель для общего ответа
class PaginatedResponse(BaseModel):
    data: List[SensorDataResponse]
    meta: PaginationMeta

# Модель SQLAlchemy
class SensorData(Base):
    __tablename__ = "sensor_data"
    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP)
    pipe_number = Column(String(10))
    sensor_type = Column(String(10))
    sensor_number = Column(Integer)
    value = Column(Float)

    __table_args__ = (
        UniqueConstraint(
            'timestamp',
            'pipe_number',
            'sensor_type',
            'sensor_number',
            name='unique_measurement'
        ),
    )

#Base.metadata.drop_all(bind=engine)  # Удалить таблицу
Base.metadata.create_all(bind=engine)

def parse_sensor_column(column_name: str) -> Optional[dict]:
    """Парсинг названий столбцов с возвратом словаря"""
    clean_name = column_name.split(" (")[0].strip()
    patterns = [
        (r"T(\d+)_([A-Za-z]+)_(\d+)",
         lambda m: {
             "pipe_number": f"T{m.group(1)}",
             "sensor_type": m.group(2),
             "sensor_number": int(m.group(3))
         }),
        (r"T_(\d+)",
         lambda m: {
             "pipe_number": f"T_{m.group(1)}",  # Исправлено формирование pipe_number
             "sensor_type": "T",
             "sensor_number": int(m.group(1))
         })
    ]

    for pattern, handler in patterns:
        match = re.match(pattern, clean_name)
        if match:
            return handler(match)
    return None

def parse_timestamp(time_str: str) -> datetime:
    """Парсинг времени с поддержкой разных форматов"""
    time_str = time_str.replace(',', '.').split('+')[0]  # Удаляем временную зону
    formats = [
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Неизвестный формат времени: {time_str}")

@app.websocket("/ws-alert")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    alert_connections.add(websocket)
    
    try:
        while True:
            await websocket.receive_text()
            
    except:
        alert_connections.remove(websocket)

# При загрузке новых данных
async def notify_clients(alert_data):
    for connection in alert_connections:
        await connection.send_json(alert_data)

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    print(f"Received file: {file.filename}") 
    try:
        contents = await file.read()
        text_contents = contents.decode('utf-8-sig')
        
        csv_reader = csv.DictReader(io.StringIO(text_contents), delimiter=';')

        if 'Time' not in csv_reader.fieldnames:
            raise HTTPException(400, "CSV файл не содержит колонку 'Time'")

        data_to_insert = []
        sensor_values = {}  # Словарь для хранения значений по сенсорам

        for row in csv_reader:
            try:
                timestamp = parse_timestamp(row['Time'])

                for col_name, value in row.items():
                    if col_name == 'Time' or not value:
                        continue

                    sensor_info = parse_sensor_column(col_name)
                    if not sensor_info:
                        continue

                    try:
                        value_float = float(value.replace(',', '.'))
                    except ValueError:
                        logging.error(f"Некорректное значение: {value}")
                        continue

                    data_to_insert.append({
                        "timestamp": timestamp,
                        "pipe_number": sensor_info["pipe_number"],
                        "sensor_type": sensor_info["sensor_type"],
                        "sensor_number": sensor_info["sensor_number"],
                        "value": value_float
                    })

                    # Сохраняем значения для вычисления min и max
                    sensor_key = f"{sensor_info['pipe_number']}_{sensor_info['sensor_type']}_{sensor_info['sensor_number']}"
                    if sensor_key not in sensor_values:
                        sensor_values[sensor_key] = []
                    sensor_values[sensor_key].append(value_float)

            except Exception as e:
                logging.error(f"Ошибка обработки строки: {str(e)}")
                continue

        # Массовая вставка с обработкой конфликтов
        alert = None
        with SessionLocal() as db:
            # Вставка данных
            stmt = insert(SensorData.__table__).on_conflict_do_nothing(
                constraint='unique_measurement'
            )
            db.execute(stmt, data_to_insert)
            db.commit()

            # Проверка оповещений для каждого сенсора
            for sensor_key, values in sensor_values.items():
                if not values:
                    continue

                min_val = min(values)
                max_val = max(values)
                avg = sum(values) / len(values)
                threshold = max(values) *0.95

                if avg > threshold:
                    alert_data = AlertResponse(
                        alert=True,
                        message=f"Критическое значение! Среднее: {avg:.2f} > Порог: {threshold:.2f} для сенсора {sensor_key}",
                        current_avg=avg,
                        threshold=threshold
                    )
                    await notify_clients(alert_data.dict())
                    alert = alert_data  # Сохраняем для ответа

        return {
            "message": "Данные загружены",
            "new_records": len(data_to_insert),
            "duplicates": "Недоступно",
            "alert": alert
        }

    except Exception as e:
        logging.error(f"Фатальная ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data/by-date", response_model=List[SensorDataResponse])
def get_data_by_date(
    sensor_id: Optional[str] = Query(None, description="Идентификатор датчика (например, T1_K_1)"),
    start_date: datetime = Query(..., description="Начальная дата для фильтрации"),
    end_date: datetime = Query(..., description="Конечная дата для фильтрации"),
    min_value: Optional[float] = Query(None, description="Минимальное значение"),
    max_value: Optional[float] = Query(None, description="Максимальное значение")
):
    with SessionLocal() as db:
        try:
            query = db.query(SensorData)

            # Фильтр по sensor_id
            if sensor_id:
                parsed = parse_sensor_column(sensor_id)
                if not parsed:
                    raise HTTPException(400, "Неверный формат sensor_id")

                query = query.filter(
                    and_(
                        SensorData.pipe_number == parsed["pipe_number"],
                        SensorData.sensor_type == parsed["sensor_type"],
                        SensorData.sensor_number == parsed["sensor_number"]
                    )
                )
                

            # Фильтр по датам
            query = query.filter(SensorData.timestamp >= start_date)
            if end_date is not None:
                query = query.filter(SensorData.timestamp <= end_date)
            if min_value is not None and max_value is not None:
                query = query.filter(SensorData.value >= min_value).filter(SensorData.value <= max_value)
            elif min_value is not None:
                query = query.filter(SensorData.value >= min_value)
            elif max_value is not None:
                query = query.filter(SensorData.value <= max_value)
            else:
                pass
            query = query.filter(SensorData.timestamp <= end_date)

            # Фильтр по значению
            if min_value is not None:
                query = query.filter(SensorData.value >= min_value)
            if max_value is not None:
                query = query.filter(SensorData.value <= max_value)

            # Получаем данные
            result = query.all()

            return [SensorDataResponse(
                timestamp=item.timestamp,
                pipe_number=item.pipe_number,
                sensor_type=item.sensor_type,
                sensor_number=item.sensor_number,
                value=item.value,
                sensor_id=f"{item.pipe_number}_{item.sensor_type}_{item.sensor_number}"
            ) for item in result]

        except Exception as e:
            logging.error(f"Ошибка: {str(e)}")
            raise HTTPException(500, "Внутренняя ошибка сервера")

@app.get("/data/by-page", response_model=PaginatedResponse)
def get_data_by_page(
    sensor_id: Optional[str] = Query(None, description="Идентификатор датчика (например, T1_K_1)"),
    start_date: Optional[datetime] = Query(None, description="Начальная дата для фильтрации"),
    end_date: Optional[datetime] = Query(None, description="Конечная дата для фильтрации"),
    min_value: Optional[float] = Query(None, description="Минимальное значение"),
    max_value: Optional[float] = Query(None, description="Максимальное значение"),
    page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
    limit: int = Query(100, ge=1, le=1000, description="Количество записей на странице")
):
    with SessionLocal() as db:
        try:
            query = db.query(SensorData)

            # Применяем фильтры
            if sensor_id:
                parsed = parse_sensor_column(sensor_id)
                if not parsed:
                    raise HTTPException(400, "Неверный формат sensor_id")
                query = query.filter(
                    and_(
                        SensorData.pipe_number == parsed["pipe_number"],
                        SensorData.sensor_type == parsed["sensor_type"],
                        SensorData.sensor_number == parsed["sensor_number"]
                    )
                )

            if start_date:
                query = query.filter(SensorData.timestamp >= start_date)
            if end_date:
                query = query.filter(SensorData.timestamp <= end_date)

            if min_value is not None:
                query = query.filter(SensorData.value >= min_value)
            if max_value is not None:
                query = query.filter(SensorData.value <= max_value)

            # Вычисляем общее количество записей
            total_count = query.count()
            
            # Вычисляем общее количество страниц
            total_pages = (total_count + limit - 1) // limit

            # Получаем данные для текущей страницы
            result = query.offset((page - 1) * limit).limit(limit).all()

            # Формируем ответ
            return PaginatedResponse(
                data=[SensorDataResponse(
                    timestamp=item.timestamp,
                    pipe_number=item.pipe_number,
                    sensor_type=item.sensor_type,
                    sensor_number=item.sensor_number,
                    value=item.value,
                    sensor_id=f"{item.pipe_number}_{item.sensor_type}_{item.sensor_number}"
                ) for item in result],
                meta=PaginationMeta(
                    total=total_count,
                    page=page,
                    limit=limit,
                    total_pages=max(total_pages, 1)  # Минимум 1 страница
                )
            )

        except Exception as e:
            logging.error(f"Ошибка: {str(e)}")
            raise HTTPException(500, "Внутренняя ошибка сервера")

@app.get("/data/csv")
def export_csv():
    def generate():
        with SessionLocal() as db:
            query = db.query(SensorData).yield_per(1000)
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["timestamp", "pipe_number", "sensor_type", "sensor_number", "value"])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

            for item in query:
                writer.writerow([
                    item.timestamp.isoformat(),
                    item.pipe_number,
                    item.sensor_type,
                    item.sensor_number,
                    item.value
                ])
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"}
    )

@app.get("/data/sensors")
def get_unique_sensors():
    with SessionLocal() as db:
        query = db.query(SensorData).distinct(SensorData.pipe_number, SensorData.sensor_type, SensorData.sensor_number)
        sensors = [f"{item.pipe_number}_{item.sensor_type}_{item.sensor_number}" for item in query]
        return {"sensors": sensors}

@app.get("/data/extremes", response_model=ExtremesResponse)
def get_extremes(
    sensor_id: Optional[str] = Query(None, description="Идентификатор датчика"),
    start_date: Optional[datetime] = Query(None, description="Начальная дата"),
    end_date: Optional[datetime] = Query(None, description="Конечная дата"),
):
    with SessionLocal() as db:
        try:
            query = db.query(
                func.min(SensorData.value).label("min"),
                func.max(SensorData.value).label("max")
            )

            # Фильтр по sensor_id
            if sensor_id:
                parsed = parse_sensor_column(sensor_id)
                if not parsed:
                    raise HTTPException(400, "Неверный формат sensor_id")
                
                query = query.filter(
                    and_(
                        SensorData.pipe_number == parsed["pipe_number"],
                        SensorData.sensor_type == parsed["sensor_type"],
                        SensorData.sensor_number == parsed["sensor_number"]
                    )
                )

            # Фильтр по датам
            if start_date:
                query = query.filter(SensorData.timestamp >= start_date)
            if end_date:
                query = query.filter(SensorData.timestamp <= end_date)

            result = query.one()
            
            return {
                "min": result.min,
                "max": result.max
            }
        
        except NoResultFound:
            return {"min": None, "max": None}
        except Exception as e:
            logging.error(f"Ошибка: {str(e)}")
            raise HTTPException(500, "Внутренняя ошибка сервера")
        
# Кэшируем на 5 минут
@app.get("/check-alert", response_model=AlertResponse)
@cache(expire=300)
async def check_alert(
    sensor_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    with SessionLocal() as db:
        try:
            # Получаем экстремальные значения
            extremes = get_extremes(
                sensor_id=sensor_id,
                start_date=start_date,
                end_date=end_date

            )
            
            
            if extremes['min'] is None or extremes['max'] is None:
                return AlertResponse(
                    alert=False,
                    message="Нет данных для анализа",
                    current_avg=None,
                    threshold=None

                )
            
            # Пример логики: порог = 90% от максимального значения
            threshold = extremes['max'] * 0.9
            avg = (extremes['min'] + extremes['max']) / 2
            alert = avg > threshold
            print(threshold, avg, alert)
            return AlertResponse(
                alert=alert,
                message=f"Среднее значение {avg:.2f} {'превысило' if alert else 'ниже'} порога {threshold:.2f}",
                current_avg=avg,
                threshold=threshold
            )
            print('h3')
        except Exception as e:
            logging.error(f"Ошибка проверки: {str(e)}", exc_info=True)
            raise HTTPException(500, "Ошибка при проверке уведомлений")