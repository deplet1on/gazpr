import { useEffect, useState } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "./ui/skeleton";
import { getSensorDataByPage } from "@/api";

export function DataTable({
  page,
  limit,
  onPageChange,
  sensorId,
  onSensorsLoaded,
}: {
  page: number;
  limit: number;
  onPageChange: (page: number) => void;
  sensorId?: string;
  onSensorsLoaded: (sensors: string[]) => void;
}) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const result = await getSensorDataByPage(
          page,
          limit,
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
  }, [page, limit, sensorId, onSensorsLoaded]);

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Время</TableHead>
            <TableHead>ID датчика</TableHead>
            <TableHead>Значение</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={3}>
                <Skeleton className="h-[20px] w-full" />
              </TableCell>
            </TableRow>
          ) : (
            data.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  {new Date(item.timestamp).toLocaleString()}
                </TableCell>
                <TableCell>{item.sensor_id}</TableCell>
                <TableCell>{item.value.toFixed(2)}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
