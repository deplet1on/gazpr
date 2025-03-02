from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, TIMESTAMP, and_, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
import csv
import io
import logging
import re
import os
from typing import Optional
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor, as_completed

# Инициализация
Base = declarative_base()
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Укажите домен фронтенда
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все методы
    allow_headers=["*"],  # Разрешить все заголовки
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

    # Уникальный индекс для предотвращения дубликатов
    __table_args__ = (
        UniqueConstraint(
            'timestamp', 
            'pipe_number', 
            'sensor_type', 
            'sensor_number',
            name='unique_measurement'
        ),
    )

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
             "pipe_number": f"T{m.group(1)}",
             "sensor_type": "T",
             "sensor_number": int(m.group(1))
         })
    ]
    
    for pattern, handler in patterns:
        match = re.match(pattern, clean_name)
        if match:
            return handler(match)
    return None

def process_row(row, db):
    """Обработка одной строки CSV и вставка в БД"""
    try:
        timestamp = datetime.strptime(
            row['Time'].replace(',', '.'), 
            '%Y-%m-%dT%H:%M:%S.%f'
        )
        
        for col_name, value in row.items():
            if col_name == 'Time': continue
            
            sensor_info = parse_sensor_column(col_name)
            if not sensor_info:
                continue

            # Проверка существования записи
            exists = db.query(SensorData).filter(
                and_(
                    SensorData.timestamp == timestamp,
                    SensorData.pipe_number == sensor_info["pipe_number"],
                    SensorData.sensor_type == sensor_info["sensor_type"],
                    SensorData.sensor_number == sensor_info["sensor_number"]
                )
            ).first()

            if not exists:
                db.add(SensorData(
                    timestamp=timestamp,
                    **sensor_info,
                    value=float(value.replace(',', '.'))
                ))
                db.commit()
                return True  # Новая запись добавлена
            else:
                return False  # Дубликат, пропуск
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в строке: {str(e)}")
        return False

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        contents = await file.read()
        text_contents = contents.decode('utf-8-sig')
        csv_reader = csv.DictReader(io.StringIO(text_contents), delimiter=';')
        
        new_records = 0
        duplicates = 0

        # Используем ThreadPoolExecutor для многопоточной обработки
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for row in csv_reader:
                futures.append(executor.submit(process_row, row, db))
            
            for future in as_completed(futures):
                if future.result():
                    new_records += 1
                else:
                    duplicates += 1

        return {
            "message": "Данные загружены",
            "new_records": new_records,
            "duplicates": duplicates
        }

    except Exception as e:
        logging.error(f"Фатальная ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        db.close()
@app.get("/data", response_model=list[SensorDataResponse])
def get_data(
    sensor_id: Optional[str] = Query(None, description="Идентификатор датчика (например, T1_K_1)"),
    start_date: Optional[datetime] = Query(None, description="Начальная дата"),
    end_date: Optional[datetime] = Query(None, description="Конечная дата"),
    min_deformation: Optional[float] = Query(None, description="Минимальный уровень деформации"),
    max_deformation: Optional[float] = Query(None, description="Максимальный уровень деформации"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, le=1000)
):
    db = SessionLocal()
    try:
        query = db.query(SensorData)
        
        # Фильтр по sensor_id
        if sensor_id:
            parsed = parse_sensor_column(sensor_id)
            if not parsed:
                raise HTTPException(status_code=400, detail="Неверный формат sensor_id")
            pipe_number, sensor_type, sensor_number = parsed.split('_')
            query = query.filter(
                and_(
                    SensorData.pipe_number == pipe_number,
                    SensorData.sensor_type == sensor_type,
                    SensorData.sensor_number == int(sensor_number)
                )
            )

        # Фильтр по дате
        if start_date and end_date:
            query = query.filter(SensorData.timestamp.between(start_date, end_date))

        # Фильтр по уровню деформации
        if min_deformation is not None:
            query = query.filter(SensorData.value >= min_deformation)
        if max_deformation is not None:
            query = query.filter(SensorData.value <= max_deformation)

        # Пагинация
        result = query.offset((page - 1) * limit).limit(limit).all()
        
        # Добавляем sensor_id в ответ
        return [{
                "timestamp": item.timestamp,
                "pipe_number": item.pipe_number,
                "sensor_type": item.sensor_type,
                "sensor_number": item.sensor_number,
                "value": item.value,
                "sensor_id": f"{item.pipe_number}_{item.sensor_type}_{item.sensor_number}"
            } for item in result]
    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    
    finally:
        db.close()

@app.get("/data/csv")
def export_csv():
    db = SessionLocal()
    try:
        data = db.query(SensorData).all()
        
        def generate():
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["timestamp", "pipe_number", "sensor_type", "sensor_number", "value"])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            
            for item in data:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()