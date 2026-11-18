'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import Cookies from 'js-cookie';
import { api } from '@/services/api';

interface User {
  id: string;
  full_name: string;
  email: string;
  role: 'SUPER_ADMIN' | 'COMPANY_ADMIN' | 'COMPANY_OPERATOR' | 'COMPANY_EXPORTER';
  company_id: string | null;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const savedToken = Cookies.get('saas_token') || localStorage.getItem('saas_token');
    const savedUser = localStorage.getItem('saas_user');

    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
  }, []);

  const login = async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password });
    const { access_token, user: userData } = response.data;

    setToken(access_token);
    setUser(userData);

    Cookies.set('saas_token', access_token, { expires: 1 });
    localStorage.setItem('saas_token', access_token);
    localStorage.setItem('saas_user', JSON.stringify(userData));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    Cookies.remove('saas_token');
    localStorage.removeItem('saas_token');
    localStorage.removeItem('saas_user');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return context;
};