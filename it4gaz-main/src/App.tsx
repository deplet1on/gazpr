import { useState } from "react";
import { DateRange } from "react-day-picker";

import { DataTable } from "./components/DataTable";
import { DatePickerWithRange } from "./components/DateRangePicker";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { ChartComponent } from "./components/ChartComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./components/ui/select";

export default function App() {
  const [dateRange, setDateRange] = useState<DateRange | undefined>();
  const [page, setPage] = useState(1);
  const [limit] = useState(100);
  const [selectedSensor, setSelectedSensor] = useState<string>("");
  const [availableSensors, setAvailableSensors] = useState<string[]>([]);

  return (
    <div className="container mx-auto p-4">
      <div className="mb-4 flex gap-2">
        <DatePickerWithRange onDateChange={setDateRange} />
        <Select onValueChange={setSelectedSensor}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Все датчики" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="выбор">Все датчики</SelectItem>
            {availableSensors.map((sensor) => (
              <SelectItem key={sensor} value={sensor}>
                {sensor}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Tabs defaultValue="chart">
        <TabsList>
          <TabsTrigger value="chart">График</TabsTrigger>
          <TabsTrigger value="table">Таблица</TabsTrigger>
        </TabsList>
        <TabsContent value="chart">
          <ChartComponent
            dateRange={dateRange}
            sensorId={selectedSensor}
            onSensorsLoaded={setAvailableSensors}
          />
        </TabsContent>
        <TabsContent value="table">
          <DataTable
            page={page}
            limit={limit}
            onPageChange={setPage}
            sensorId={selectedSensor}
            onSensorsLoaded={setAvailableSensors}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
