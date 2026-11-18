import axios from 'axios';
import Cookies from 'js-cookie';

// URL del backend FastAPI en ejecución
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para inyectar automáticamente el Bearer Token JWT en cada petición
api.interceptors.request.use((config) => {
  const token = Cookies.get('saas_token') || localStorage.getItem('saas_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});