from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import UniqueConstraint, create_engine, Column, Integer, String, Float, TIMESTAMP, and_, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
import csv
import io
import logging
import re
import os
from typing import Optional, List
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.dialects.postgresql import insert

# Инициализация
Base = declarative_base()
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, connect_args={"client_encoding": "UTF8"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

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

    class Config:
        orm_mode = True

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

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        text_contents = contents.decode('utf-8-sig')
        csv_reader = csv.DictReader(io.StringIO(text_contents), delimiter=';')
        
        if 'Time' not in csv_reader.fieldnames:
            raise HTTPException(400, "CSV файл не содержит колонку 'Time'")

        data_to_insert = []
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
            except Exception as e:
                logging.error(f"Ошибка обработки строки: {str(e)}")
                continue

        # Массовая вставка с обработкой конфликтов
        stmt = insert(SensorData.__table__).on_conflict_do_nothing(
            constraint='unique_measurement'  # Используем имя ограничения
        )
        with SessionLocal() as db:
            db.execute(stmt, data_to_insert)
            db.commit()

        return {
            "message": "Данные загружены",
            "new_records": len(data_to_insert),  # Примерное количество новых записей
            "duplicates": "Недоступно (используйте расширенный анализ)"
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
        
@app.get("/data/by-page", response_model=List[SensorDataResponse])
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

            # Фильтр по значению
            if min_value is not None:
                query = query.filter(SensorData.value >= min_value)
            if max_value is not None:
                query = query.filter(SensorData.value <= max_value)

            # Пагинация
            result = query.offset((page - 1) * limit).limit(limit).all()
            
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