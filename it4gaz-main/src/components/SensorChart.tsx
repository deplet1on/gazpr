import {
  AreaChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Area,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import { TransformedData } from "@/api";

export function SensorChart({
  selectedSensors,
  sensorData,
  startDate,
  endDate,
}: {
  selectedSensors: string[];
  sensorData: TransformedData[];
  startDate: string;
  endDate: string;
}) {
  // Преобразуем данные для графика
  const chartData = sensorData.map((data) => ({
    timestamp: format(parseISO(data.timestamp), "HH:mm"),
    ...Object.fromEntries(
      selectedSensors.map((sensor) => [sensor, data[sensor] || null])
    ),
  }));

  return (
    <div>
      <h3>
        Показания датчиков с {startDate} по {endDate}
      </h3>
      <AreaChart width={800} height={400} data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" />
        <YAxis domain={["auto", "auto"]} /> {/* Устанавливаем диапазон оси Y */}
        <Tooltip />
        <Legend />
        {selectedSensors.map((sensor, index) => (
          <Area
            key={sensor}
            type="monotone"
            dataKey={sensor}
            stroke={`#${Math.floor(Math.random() * 16777215).toString(16)}`}
            fill={`#${Math.floor(Math.random() * 16777215).toString(16)}`}
            fillOpacity={0.3}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </div>
  );
}
