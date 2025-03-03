export interface SensorData {
  timestamp: string;
  [sensorId: string]: number | string;
}

const generateMockData = (): SensorData[] => {
  const sensors = [
    'T1_K_1', 'T1_K_3', 'T1_K_2', 
    'T1_L_1', 'T1_L_2', 'T1_L_3',
    'T1_R_1', 'T1_R_2', 'T1_R_3',
    'T1_Up_1', 'T1_Up_2', 'T1_Up_3', 
    'T_1'
  ];

  return Array.from({ length: 100 }, (_, i) => {
    const date = new Date(2024, 0, 1);
    date.setHours(date.getHours() + i);
    
    const dataPoint: SensorData = {
      timestamp: date.toISOString()
    };

    sensors.forEach(sensor => {
      dataPoint[sensor] = Number((Math.random() * 100).toFixed(2));
    });

    return dataPoint;
  });
};

export const mockSensorData = generateMockData();
export const sensorOptions = mockSensorData
  .reduce((acc: string[], curr) => {
    Object.keys(curr).forEach(key => {
      if (key !== 'timestamp' && !acc.includes(key)) acc.push(key);
    });
    return acc;
  }, []);