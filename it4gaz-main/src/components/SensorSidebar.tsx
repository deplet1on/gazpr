import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Checkbox } from "./ui/checkbox";

interface SensorSidebarProps {
  selectedSensors: string[];
  setSelectedSensors: (sensors: string[]) => void;
  sensorOptions: string[]; // Добавляем sensorOptions
}

export const SensorSidebar = ({
  selectedSensors,
  setSelectedSensors,
  sensorOptions,
}: SensorSidebarProps) => {
  const handleSensorSelect = (sensor: string) => {
    setSelectedSensors(
      selectedSensors.includes(sensor)
        ? selectedSensors.filter((s) => s !== sensor)
        : [...selectedSensors, sensor]
    );
  };

  return (
    <Card className="mb-8">
      <CardHeader>
        <CardTitle className="text-lg font-bold mb-4">Выбор датчиков</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {sensorOptions.map((sensor) => (
            <label key={sensor} className="flex items-center gap-2">
              <Checkbox
                checked={selectedSensors.includes(sensor)}
                onCheckedChange={() => handleSensorSelect(sensor)}
              />
              <span className="text-sm">{sensor}</span>
            </label>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
