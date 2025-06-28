import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { type Echo } from '../types';
import { echoService } from '../services/echoService';

interface EchoContextType {
  echoes: Echo[];
  currentEcho: Echo | null;
  loading: boolean;
  fetchEchoes: (emotion?: string) => Promise<void>;
  getRandomEcho: (emotion?: string) => Promise<Echo | null>;
  saveEcho: (echo: Omit<Echo, 'echoId' | 'timestamp'>) => Promise<Echo>;
  deleteEcho: (echoId: string) => Promise<void>;
  setCurrentEcho: (echo: Echo | null) => void;
  refreshEchoes: () => Promise<void>;
}

const EchoContext = createContext<EchoContextType | undefined>(undefined);

export const useEchoes = () => {
  const context = useContext(EchoContext);
  if (context === undefined) {
    throw new Error('useEchoes must be used within an EchoProvider');
  }
  return context;
};

interface EchoProviderProps {
  children: ReactNode;
}

export const EchoProvider: React.FC<EchoProviderProps> = ({ children }) => {
  const [echoes, setEchoes] = useState<Echo[]>([]);
  const [currentEcho, setCurrentEcho] = useState<Echo | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchEchoes = async (emotion?: string) => {
    setLoading(true);
    try {
      const fetchedEchoes = await echoService.getEchoes(emotion);
      setEchoes(fetchedEchoes);
    } catch (error) {
      console.error('Failed to fetch echoes:', error);
    } finally {
      setLoading(false);
    }
  };

  const getRandomEcho = async (emotion?: string) => {
    setLoading(true);
    try {
      const echo = await echoService.getRandomEcho(emotion);
      return echo;
    } catch (error) {
      console.error('Failed to get random echo:', error);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const saveEcho = async (echoData: Omit<Echo, 'echoId' | 'timestamp'>) => {
    setLoading(true);
    try {
      const savedEcho = await echoService.saveEcho(echoData);
      setEchoes(prev => [savedEcho, ...prev]);
      return savedEcho;
    } catch (error) {
      console.error('Failed to save echo:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const deleteEcho = async (echoId: string) => {
    setLoading(true);
    try {
      await echoService.deleteEcho(echoId);
      setEchoes(prev => prev.filter(echo => echo.echoId !== echoId));
      if (currentEcho?.echoId === echoId) {
        setCurrentEcho(null);
      }
    } catch (error) {
      console.error('Failed to delete echo:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const refreshEchoes = async () => {
    await fetchEchoes();
  };

  // Initial load
  useEffect(() => {
    fetchEchoes();
  }, []);

  const value = {
    echoes,
    currentEcho,
    loading,
    fetchEchoes,
    getRandomEcho,
    saveEcho,
    deleteEcho,
    setCurrentEcho,
    refreshEchoes,
  };

  return <EchoContext.Provider value={value}>{children}</EchoContext.Provider>;
};