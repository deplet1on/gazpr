import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { DateRange } from "react-day-picker";

import { Skeleton } from "@/components/ui/skeleton";
import { getSensorDataByDate } from "@/api";

export function ChartComponent({
  dateRange,
  sensorId,
  onSensorsLoaded,
}: {
  dateRange?: DateRange;
  sensorId?: string;
  onSensorsLoaded: (sensors: string[]) => void;
}) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      if (!dateRange?.from || !dateRange?.to) return;

      setLoading(true);
      try {
        const result = await getSensorDataByDate(
          dateRange.from.toISOString().split("T")[0],
          dateRange.to.toISOString().split("T")[0],
          sensorId || undefined
        );

        // Обновляем список доступных датчиков
        const sensors = Array.from(
          new Set(result.map((item) => item.sensor_id))
        );
        onSensorsLoaded(sensors);

        setData(result);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [dateRange, sensorId, onSensorsLoaded]);

  if (loading) return <Skeleton className="h-[400px] w-full" />;

  return (
    <div className="h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(time) => new Date(time).toLocaleDateString()}
          />
          <YAxis />
          <Tooltip
            labelFormatter={(value) => new Date(value).toLocaleString()}
          />
          <Line type="monotone" dataKey="value" stroke="#8884d8" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
