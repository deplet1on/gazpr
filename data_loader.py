import csv
import re
from datetime import datetime
from sqlalchemy import create_engine, Table, Column, MetaData, exc
from sqlalchemy.types import String, Float, TIMESTAMP, Integer
import logging
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
DATABASE_URL = os.getenv("DATABASE_URL")
CSV_FILE_PATH = "case_1.csv"
BATCH_SIZE = 1000

# Логирование
logging.basicConfig(
    filename='data_loading.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

engine = create_engine(DATABASE_URL)
metadata = MetaData()

sensor_data = Table(
    'sensor_data', metadata,
    Column('id', Integer, primary_key=True),
    Column('timestamp', TIMESTAMP),
    Column('pipe_number', String(10)),
    Column('sensor_type', String(10)),
    Column('sensor_number', Integer),
    Column('value', Float)
)

loading_errors = Table(
    'loading_errors', metadata,
    Column('id', Integer, primary_key=True),
    Column('error_message', String),
    Column('raw_data', String),
    Column('created_at', TIMESTAMP)
)

def parse_sensor_column(column_name):
    """Парсинг названия колонки CSV."""
    patterns = [
        (r"T(\d+)_([A-Za-z]+)_(\d+).*", lambda m: (f"T{m.group(1)}", m.group(2), int(m.group(3)))),
        (r"T_(\d+).*", lambda m: (f"T{m.group(1)}", "T", int(m.group(1))))
    ]
    for pattern, handler in patterns:
        match = re.match(pattern, column_name)
        if match:
            return handler(match)
    return None

def log_error(error_msg, raw_data=None):
    """Логирование ошибок."""
    logging.error(f"{error_msg} | Raw data: {raw_data}")
    try:
        with engine.connect() as conn:
            conn.execute(
                loading_errors.insert().values(
                    error_message=error_msg,
                    raw_data=str(raw_data)[:500]
                )
            )
    except Exception as e:
        logging.error(f"Ошибка логирования: {str(e)}")

def load_csv():
    """Загрузка данных в БД."""
    try:
        with open(CSV_FILE_PATH, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file, delimiter=';')
            buffer = []
            
            for row in csv_reader:
                try:
                    timestamp = datetime.strptime(
                        row['Time'].replace(',', '.'),
                        '%Y-%m-%dT%H:%M:%S.%f'
                    )
                    
                    for col, val in row.items():
                        if col == 'Time':
                            continue
                        
                        sensor_info = parse_sensor_column(col)
                        if not sensor_info:
                            log_error(f"Неверный формат колонки: {col}", row)
                            continue
                        
                        pipe, sensor_type, sensor_num = sensor_info
                        value = float(val.replace(',', '.'))
                        
                        buffer.append({
                            'timestamp': timestamp,
                            'pipe_number': pipe,
                            'sensor_type': sensor_type,
                            'sensor_number': sensor_num,
                            'value': value
                        })
                        
                        if len(buffer) >= BATCH_SIZE:
                            with engine.begin() as conn:
                                conn.execute(sensor_data.insert(), buffer)
                            buffer = []
                    
                    if buffer:
                        with engine.begin() as conn:
                            conn.execute(sensor_data.insert(), buffer)
                        buffer = []
                        
                except Exception as e:
                    log_error(f"Ошибка строки: {str(e)}", row)
                    
    except Exception as e:
        log_error(f"Фатальная ошибка: {str(e)}")

if __name__ == "__main__":
    load_csv()