-- Создание таблицы для данных датчиков
CREATE TABLE IF NOT EXISTS sensor_data (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    pipe_number VARCHAR(10) NOT NULL,
    sensor_type VARCHAR(10) NOT NULL,
    sensor_number INTEGER NOT NULL,
    value FLOAT NOT NULL
);

-- Создание таблицы для ошибок загрузки
CREATE TABLE IF NOT EXISTS loading_errors (
    id SERIAL PRIMARY KEY,
    error_message TEXT NOT NULL,
    raw_data TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для оптимизации
CREATE INDEX idx_pipe_number ON sensor_data (pipe_number);
CREATE INDEX idx_sensor_type ON sensor_data (sensor_type);
CREATE INDEX idx_timestamp ON sensor_data (timestamp);