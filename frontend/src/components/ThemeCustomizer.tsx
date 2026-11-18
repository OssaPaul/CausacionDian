'use client';

import React, { useState, useEffect } from 'react';
import { Sun, Moon, Palette } from 'lucide-react';

export const ThemeCustomizer = () => {
  const [mode, setMode] = useState<'dark' | 'light'>('dark');
  const [bgColor, setBgColor] = useState('#0f172a');
  const [textColor, setTextColor] = useState('#f8fafc');

  useEffect(() => {
    const savedMode = (localStorage.getItem('saas_theme_mode') as 'dark' | 'light') || 'dark';
    const savedBg = localStorage.getItem('saas_bg_color') || '#0f172a';
    const savedText = localStorage.getItem('saas_text_color') || '#f8fafc';

    setMode(savedMode);
    setBgColor(savedBg);
    setTextColor(savedText);
    applyTheme(savedMode, savedBg, savedText);
  }, []);

  const applyTheme = (currentMode: 'dark' | 'light', bg: string, text: string) => {
    const root = document.documentElement;
    if (currentMode === 'light') {
      root.classList.add('light');
      root.classList.remove('dark');
    } else {
      root.classList.add('dark');
      root.classList.remove('light');
    }
    root.style.setProperty('--custom-bg', bg);
    root.style.setProperty('--custom-text', text);
  };

  const handleModeChange = (newMode: 'dark' | 'light') => {
    setMode(newMode);
    localStorage.setItem('saas_theme_mode', newMode);
    const defaultBg = newMode === 'light' ? '#f1f5f9' : '#0f172a';
    const defaultText = newMode === 'light' ? '#0f172a' : '#f8fafc';
    setBgColor(defaultBg);
    setTextColor(defaultText);
    applyTheme(newMode, defaultBg, defaultText);
  };

  const handleColorChange = (newBg: string, newText: string) => {
    setBgColor(newBg);
    setTextColor(newText);
    localStorage.setItem('saas_bg_color', newBg);
    localStorage.setItem('saas_text_color', newText);
    applyTheme(mode, newBg, newText);
  };

  return (
    <div className="p-4 bg-slate-800/50 dark:bg-slate-900/50 border border-slate-700/50 rounded-xl space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold uppercase text-slate-400">Modo de Pantalla</span>
        <button
          onClick={() => handleModeChange(mode === 'dark' ? 'light' : 'dark')}
          className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition"
        >
          {mode === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
        </button>
      </div>

      <div>
        <div className="flex items-center space-x-2 text-xs font-bold uppercase text-slate-400 mb-2">
          <Palette className="w-3.5 h-3.5" />
          <span>Colores Personalizados</span>
        </div>
        <div className="flex items-center justify-between text-xs text-slate-300">
          <label className="flex items-center space-x-2">
            <span>Fondo:</span>
            <input
              type="color"
              value={bgColor}
              onChange={(e) => handleColorChange(e.target.value, textColor)}
              className="w-6 h-6 rounded border-none bg-transparent cursor-pointer"
            />
          </label>
          <label className="flex items-center space-x-2">
            <span>Texto:</span>
            <input
              type="color"
              value={textColor}
              onChange={(e) => handleColorChange(bgColor, e.target.value)}
              className="w-6 h-6 rounded border-none bg-transparent cursor-pointer"
            />
          </label>
        </div>
      </div>
    </div>
  );
};