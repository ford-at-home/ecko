/**
 * Tests for HomeScreen component
 * Tests the "I feel [x]..." functionality and echo resurfacing
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HomeScreen } from '../../../src/components/HomeScreen';
import { AuthContext } from '../../../src/contexts/AuthContext';
import { EchoContext } from '../../../src/contexts/EchoContext';

// Mock react-navigation
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({
    navigate: jest.fn(),
    goBack: jest.fn(),
  }),
  useFocusEffect: jest.fn(),
}));

describe('HomeScreen', () => {
  const mockUser = createMockUser();
  const mockEcho = createMockEcho();
  
  const defaultContextValues = {
    auth: {
      user: mockUser,
      isAuthenticated: true,
      login: jest.fn(),
      logout: jest.fn(),
    },
    echo: {
      echoes: [mockEcho],
      getRandomEcho: jest.fn(),
      currentEcho: null,
      isLoading: false,
      error: null,
    },
  };

  const renderHomeScreen = (contextOverrides = {}) => {
    const authContextValue = { ...defaultContextValues.auth, ...contextOverrides.auth };
    const echoContextValue = { ...defaultContextValues.echo, ...contextOverrides.echo };

    return render(
      <AuthContext.Provider value={authContextValue}>
        <EchoContext.Provider value={echoContextValue}>
          <HomeScreen />
        </EchoContext.Provider>
      </AuthContext.Provider>
    );
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Initial Render', () => {
    it('renders the emotion input interface', () => {
      renderHomeScreen();
      
      expect(screen.getByText('I feel...')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('joyful, nostalgic, peaceful...')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /find echo/i })).toBeInTheDocument();
    });

    it('displays welcome message for new users', () => {
      renderHomeScreen({
        echo: { echoes: [], getRandomEcho: jest.fn() }
      });
      
      expect(screen.getByText(/welcome to echoes/i)).toBeInTheDocument();
      expect(screen.getByText(/capture your first moment/i)).toBeInTheDocument();
    });

    it('shows emotion suggestions', () => {
      renderHomeScreen();
      
      const emotionSuggestions = ['joy', 'calm', 'nostalgic', 'peaceful', 'energetic'];
      emotionSuggestions.forEach(emotion => {
        expect(screen.getByText(emotion)).toBeInTheDocument();
      });
    });
  });

  describe('Emotion Input', () => {
    it('allows typing custom emotions', async () => {
      const user = userEvent.setup();
      renderHomeScreen();
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      await user.type(input, 'melancholic');
      
      expect(input).toHaveValue('melancholic');
    });

    it('suggests emotions as user types', async () => {
      const user = userEvent.setup();
      renderHomeScreen();
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      await user.type(input, 'jo');
      
      expect(screen.getByText('joy')).toBeVisible();
      expect(screen.getByText('joyful')).toBeVisible();
    });

    it('selects emotion from suggestions', async () => {
      const user = userEvent.setup();
      renderHomeScreen();
      
      await user.click(screen.getByText('calm'));
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      expect(input).toHaveValue('calm');
    });
  });

  describe('Echo Discovery', () => {
    it('finds matching echo when emotion is entered', async () => {
      const user = userEvent.setup();
      const mockGetRandomEcho = jest.fn().mockResolvedValue(mockEcho);
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo, 
          getRandomEcho: mockGetRandomEcho 
        }
      });
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      const button = screen.getByRole('button', { name: /find echo/i });
      
      await user.type(input, 'joy');
      await user.click(button);
      
      expect(mockGetRandomEcho).toHaveBeenCalledWith('joy', mockUser.userId);
      
      await waitFor(() => {
        expect(screen.getByText('Found an echo...')).toBeInTheDocument();
      });
    });

    it('shows no echo found message when no matches', async () => {
      const user = userEvent.setup();
      const mockGetRandomEcho = jest.fn().mockResolvedValue(null);
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo, 
          getRandomEcho: mockGetRandomEcho 
        }
      });
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      const button = screen.getByRole('button', { name: /find echo/i });
      
      await user.type(input, 'sadness');
      await user.click(button);
      
      await waitFor(() => {
        expect(screen.getByText(/no echoes found/i)).toBeInTheDocument();
        expect(screen.getByText(/create your first/i)).toBeInTheDocument();
      });
    });

    it('displays loading state during echo search', async () => {
      const user = userEvent.setup();
      const mockGetRandomEcho = jest.fn(() => new Promise(resolve => setTimeout(() => resolve(mockEcho), 1000)));
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo, 
          getRandomEcho: mockGetRandomEcho,
          isLoading: true
        }
      });
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      const button = screen.getByRole('button', { name: /find echo/i });
      
      await user.type(input, 'joy');
      await user.click(button);
      
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
      expect(screen.getByText(/searching for echoes/i)).toBeInTheDocument();
    });
  });

  describe('Echo Playback Preview', () => {
    it('displays echo details when found', async () => {
      const user = userEvent.setup();
      const mockGetRandomEcho = jest.fn().mockResolvedValue(mockEcho);
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo, 
          getRandomEcho: mockGetRandomEcho,
          currentEcho: mockEcho
        }
      });
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      const button = screen.getByRole('button', { name: /find echo/i });
      
      await user.type(input, 'joy');
      await user.click(button);
      
      await waitFor(() => {
        expect(screen.getByText(mockEcho.emotion)).toBeInTheDocument();
        expect(screen.getByText(/from/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /view details/i })).toBeInTheDocument();
      });
    });

    it('plays echo preview on play button click', async () => {
      const user = userEvent.setup();
      const mockPlay = jest.fn();
      
      // Mock Audio constructor
      const mockAudio = { play: mockPlay, pause: jest.fn(), addEventListener: jest.fn() };
      global.Audio = jest.fn(() => mockAudio);
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo,
          currentEcho: mockEcho
        }
      });
      
      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);
      
      expect(mockPlay).toHaveBeenCalled();
    });
  });

  describe('Navigation', () => {
    const mockNavigate = jest.fn();
    
    beforeEach(() => {
      jest.doMock('@react-navigation/native', () => ({
        useNavigation: () => ({ navigate: mockNavigate }),
      }));
    });

    it('navigates to record screen when no echoes exist', async () => {
      const user = userEvent.setup();
      
      renderHomeScreen({
        echo: { echoes: [], getRandomEcho: jest.fn() }
      });
      
      const createButton = screen.getByRole('button', { name: /create your first echo/i });
      await user.click(createButton);
      
      expect(mockNavigate).toHaveBeenCalledWith('Record');
    });

    it('navigates to playback screen from echo preview', async () => {
      const user = userEvent.setup();
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo,
          currentEcho: mockEcho
        }
      });
      
      const viewDetailsButton = screen.getByRole('button', { name: /view details/i });
      await user.click(viewDetailsButton);
      
      expect(mockNavigate).toHaveBeenCalledWith('Playback', { echo: mockEcho });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      renderHomeScreen();
      
      expect(screen.getByLabelText(/emotion input/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /find echo/i })).toBeInTheDocument();
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      renderHomeScreen();
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      const button = screen.getByRole('button', { name: /find echo/i });
      
      await user.tab();
      expect(input).toHaveFocus();
      
      await user.tab();
      expect(button).toHaveFocus();
    });

    it('announces screen reader updates', async () => {
      const user = userEvent.setup();
      const mockGetRandomEcho = jest.fn().mockResolvedValue(mockEcho);
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo, 
          getRandomEcho: mockGetRandomEcho 
        }
      });
      
      const button = screen.getByRole('button', { name: /find echo/i });
      await user.click(button);
      
      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent(/found an echo/i);
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when echo search fails', async () => {
      const user = userEvent.setup();
      const mockGetRandomEcho = jest.fn().mockRejectedValue(new Error('Network error'));
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo, 
          getRandomEcho: mockGetRandomEcho,
          error: 'Failed to search for echoes'
        }
      });
      
      const input = screen.getByPlaceholderText('joyful, nostalgic, peaceful...');
      const button = screen.getByRole('button', { name: /find echo/i });
      
      await user.type(input, 'joy');
      await user.click(button);
      
      await waitFor(() => {
        expect(screen.getByText(/failed to search for echoes/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });

    it('retries search on error button click', async () => {
      const user = userEvent.setup();
      const mockGetRandomEcho = jest.fn()
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockEcho);
      
      renderHomeScreen({
        echo: { 
          ...defaultContextValues.echo, 
          getRandomEcho: mockGetRandomEcho,
          error: 'Failed to search for echoes'
        }
      });
      
      const retryButton = screen.getByRole('button', { name: /try again/i });
      await user.click(retryButton);
      
      expect(mockGetRandomEcho).toHaveBeenCalledTimes(1);
    });
  });
});