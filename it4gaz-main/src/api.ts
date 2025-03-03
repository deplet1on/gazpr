import axios from 'axios'

const API_BASE = 'http://26.148.34.69:8000'

export const getSensorDataByDate = async (
  start: string, 
  end: string, 
  sensorId?: string
) => {
  const response = await axios.get(`${API_BASE}/data/by-date`, {
    params: { 
      start_date: start, 
      end_date: end,
      sensor_id: sensorId 
    }
  })
  return response.data
}

export const getSensorDataByPage = async (
  page: number, 
  limit: number, 
  sensorId?: string
) => {
  const response = await axios.get(`${API_BASE}/data/by-page`, {
    params: { 
      page, 
      limit,
      sensor_id: sensorId 
    }
  })
  return response.data
}