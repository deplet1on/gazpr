import { fetchSensorDataByPage, TransformedData } from "@/api";
import { useEffect, useState } from "react";

export const useSensorData = (
  startDate: string,
  endDate: string,
  page: number
) => {
  const [rawData, setRawData] = useState<TransformedData[]>([]);
  const [selectedSensors, setSelectedSensors] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const { transformedData } = await fetchSensorDataByPage(
          startDate,
          endDate,
          page
        );
        setRawData(transformedData);
        setError(null); // сбрасываем ошибку при успешной загрузке
      } catch (err) {
        console.error("Ошибка загрузки данных:", err);
        setError("Ошибка загрузки данных с сервера");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [startDate, endDate, page]);

  return {
    rawData,
    selectedSensors,
    setSelectedSensors,
    loading,
    error,
  };
};
