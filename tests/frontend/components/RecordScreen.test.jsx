/**
 * Tests for RecordScreen component
 * Tests emotion tagging, audio recording, and save functionality
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RecordScreen } from '../../../src/components/RecordScreen';
import { AuthContext } from '../../../src/contexts/AuthContext';
import { EchoContext } from '../../../src/contexts/EchoContext';

// Mock react-navigation
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({
    navigate: mockNavigate,
    goBack: mockGoBack,
  }),
  useFocusEffect: jest.fn(),
}));

describe('RecordScreen', () => {
  const mockUser = createMockUser();
  const mockEcho = createMockEcho();
  
  const defaultContextValues = {
    auth: {
      user: mockUser,
      isAuthenticated: true,
    },
    echo: {
      createEcho: jest.fn(),
      uploadAudio: jest.fn(),
      isLoading: false,
      error: null,
    },
  };

  const renderRecordScreen = (contextOverrides = {}) => {
    const authContextValue = { ...defaultContextValues.auth, ...contextOverrides.auth };
    const echoContextValue = { ...defaultContextValues.echo, ...contextOverrides.echo };

    return render(
      <AuthContext.Provider value={authContextValue}>
        <EchoContext.Provider value={echoContextValue}>
          <RecordScreen />
        </EchoContext.Provider>
      </AuthContext.Provider>
    );
  };

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Reset MediaRecorder mock
    global.MediaRecorder = jest.fn().mockImplementation(() => ({
      start: jest.fn(),
      stop: jest.fn(),
      pause: jest.fn(),
      resume: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      state: 'inactive',
      stream: null,
      ondataavailable: null,
      onstop: null,
    }));
  });

  describe('Initial Render', () => {
    it('renders emotion selection interface', () => {
      renderRecordScreen();
      
      expect(screen.getByText('How are you feeling?')).toBeInTheDocument();
      expect(screen.getByText('Choose an emotion to capture this moment')).toBeInTheDocument();
      
      // Check for emotion buttons
      const emotions = ['Joy', 'Calm', 'Nostalgic', 'Peaceful', 'Energetic', 'Melancholic'];
      emotions.forEach(emotion => {
        expect(screen.getByRole('button', { name: emotion })).toBeInTheDocument();
      });
    });

    it('shows custom emotion input option', () => {
      renderRecordScreen();
      
      expect(screen.getByRole('button', { name: /other/i })).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Enter custom emotion...')).toBeInTheDocument();
    });

    it('disables record button when no emotion selected', () => {
      renderRecordScreen();
      
      const recordButton = screen.getByRole('button', { name: /start recording/i });
      expect(recordButton).toBeDisabled();
    });
  });

  describe('Emotion Selection', () => {
    it('selects predefined emotion', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      const joyButton = screen.getByRole('button', { name: 'Joy' });
      await user.click(joyButton);
      
      expect(joyButton).toHaveClass('selected');
      expect(screen.getByRole('button', { name: /start recording/i })).toBeEnabled();
    });

    it('allows custom emotion input', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      const otherButton = screen.getByRole('button', { name: /other/i });
      await user.click(otherButton);
      
      const customInput = screen.getByPlaceholderText('Enter custom emotion...');
      await user.type(customInput, 'contemplative');
      
      expect(customInput).toHaveValue('contemplative');
      expect(screen.getByRole('button', { name: /start recording/i })).toBeEnabled();
    });

    it('validates custom emotion length', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      const otherButton = screen.getByRole('button', { name: /other/i });
      await user.click(otherButton);
      
      const customInput = screen.getByPlaceholderText('Enter custom emotion...');
      await user.type(customInput, 'a'); // Too short
      
      expect(screen.getByText(/emotion must be at least 2 characters/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /start recording/i })).toBeDisabled();
    });

    it('changes emotion selection', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      // Select first emotion
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      expect(screen.getByRole('button', { name: 'Joy' })).toHaveClass('selected');
      
      // Select different emotion
      await user.click(screen.getByRole('button', { name: 'Calm' }));
      expect(screen.getByRole('button', { name: 'Joy' })).not.toHaveClass('selected');
      expect(screen.getByRole('button', { name: 'Calm' })).toHaveClass('selected');
    });
  });

  describe('Audio Recording', () => {
    it('starts recording when button is clicked', async () => {
      const user = userEvent.setup();
      const mockStart = jest.fn();
      const mockMediaRecorder = {
        start: mockStart,
        stop: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        state: 'inactive',
      };
      
      global.MediaRecorder = jest.fn(() => mockMediaRecorder);
      
      renderRecordScreen();
      
      // Select emotion first
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      
      // Start recording
      const recordButton = screen.getByRole('button', { name: /start recording/i });
      await user.click(recordButton);
      
      expect(mockStart).toHaveBeenCalled();
      expect(screen.getByText(/recording/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /stop recording/i })).toBeInTheDocument();
    });

    it('shows recording timer', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      expect(screen.getByTestId('recording-timer')).toBeInTheDocument();
      expect(screen.getByText('00:00')).toBeInTheDocument();
    });

    it('stops recording when stop button is clicked', async () => {
      const user = userEvent.setup();
      const mockStop = jest.fn();
      const mockMediaRecorder = {
        start: jest.fn(),
        stop: mockStop,
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        state: 'recording',
      };
      
      global.MediaRecorder = jest.fn(() => mockMediaRecorder);
      
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      const stopButton = screen.getByRole('button', { name: /stop recording/i });
      await user.click(stopButton);
      
      expect(mockStop).toHaveBeenCalled();
    });

    it('enforces maximum recording duration', async () => {
      const user = userEvent.setup();
      const mockStop = jest.fn();
      const mockMediaRecorder = {
        start: jest.fn(),
        stop: mockStop,
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        state: 'recording',
      };
      
      global.MediaRecorder = jest.fn(() => mockMediaRecorder);
      
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      // Simulate 30 seconds passing
      jest.advanceTimersByTime(30000);
      
      await waitFor(() => {
        expect(mockStop).toHaveBeenCalled();
        expect(screen.getByText(/maximum recording time reached/i)).toBeInTheDocument();
      });
    });

    it('shows audio waveform visualization during recording', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      expect(screen.getByTestId('audio-waveform')).toBeInTheDocument();
    });
  });

  describe('Audio Playback', () => {
    it('allows playback of recorded audio', async () => {
      const user = userEvent.setup();
      const mockPlay = jest.fn();
      const mockAudio = { play: mockPlay, pause: jest.fn(), addEventListener: jest.fn() };
      global.Audio = jest.fn(() => mockAudio);
      
      renderRecordScreen();
      
      // Complete recording flow
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      await user.click(screen.getByRole('button', { name: /stop recording/i }));
      
      // Play recorded audio
      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);
      
      expect(mockPlay).toHaveBeenCalled();
    });

    it('shows recording duration', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      // Simulate 5 seconds of recording
      jest.advanceTimersByTime(5000);
      
      await user.click(screen.getByRole('button', { name: /stop recording/i }));
      
      expect(screen.getByText('Duration: 00:05')).toBeInTheDocument();
    });

    it('allows re-recording', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      // Complete initial recording
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      await user.click(screen.getByRole('button', { name: /stop recording/i }));
      
      // Re-record
      const reRecordButton = screen.getByRole('button', { name: /record again/i });
      await user.click(reRecordButton);
      
      expect(screen.getByRole('button', { name: /start recording/i })).toBeEnabled();
      expect(screen.queryByRole('button', { name: /play/i })).not.toBeInTheDocument();
    });
  });

  describe('Location Capture', () => {
    it('requests location permission on record start', async () => {
      const user = userEvent.setup();
      const mockGetCurrentPosition = jest.fn();
      navigator.geolocation.getCurrentPosition = mockGetCurrentPosition;
      
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      expect(mockGetCurrentPosition).toHaveBeenCalled();
    });

    it('handles location permission denial gracefully', async () => {
      const user = userEvent.setup();
      navigator.geolocation.getCurrentPosition = jest.fn((success, error) => {
        error({ code: 1, message: 'Permission denied' });
      });
      
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      // Should still allow recording without location
      expect(screen.getByText(/recording/i)).toBeInTheDocument();
      expect(screen.getByText(/location unavailable/i)).toBeInTheDocument();
    });

    it('displays current location when available', async () => {
      const user = userEvent.setup();
      navigator.geolocation.getCurrentPosition = jest.fn((success) => {
        success({
          coords: { latitude: 37.5407, longitude: -77.4360 }
        });
      });
      
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/current location/i)).toBeInTheDocument();
      });
    });
  });

  describe('Echo Saving', () => {
    it('saves echo with all metadata', async () => {
      const user = userEvent.setup();
      const mockCreateEcho = jest.fn().mockResolvedValue(mockEcho);
      const mockUploadAudio = jest.fn().mockResolvedValue('https://s3.amazonaws.com/test-url');
      
      renderRecordScreen({
        echo: {
          ...defaultContextValues.echo,
          createEcho: mockCreateEcho,
          uploadAudio: mockUploadAudio
        }
      });
      
      // Complete recording and save
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      await user.click(screen.getByRole('button', { name: /stop recording/i }));
      
      const saveButton = screen.getByRole('button', { name: /save echo/i });
      await user.click(saveButton);
      
      await waitFor(() => {
        expect(mockUploadAudio).toHaveBeenCalled();
        expect(mockCreateEcho).toHaveBeenCalledWith(
          expect.objectContaining({
            emotion: 'Joy',
            userId: mockUser.userId,
          })
        );
      });
    });

    it('shows saving progress', async () => {
      const user = userEvent.setup();
      const mockCreateEcho = jest.fn(() => new Promise(resolve => setTimeout(() => resolve(mockEcho), 1000)));
      
      renderRecordScreen({
        echo: {
          ...defaultContextValues.echo,
          createEcho: mockCreateEcho,
          isLoading: true
        }
      });
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      await user.click(screen.getByRole('button', { name: /stop recording/i }));
      
      const saveButton = screen.getByRole('button', { name: /save echo/i });
      await user.click(saveButton);
      
      expect(screen.getByText(/saving echo/i)).toBeInTheDocument();
      expect(screen.getByTestId('saving-progress')).toBeInTheDocument();
    });

    it('navigates to home after successful save', async () => {
      const user = userEvent.setup();
      const mockCreateEcho = jest.fn().mockResolvedValue(mockEcho);
      
      renderRecordScreen({
        echo: {
          ...defaultContextValues.echo,
          createEcho: mockCreateEcho
        }
      });
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      await user.click(screen.getByRole('button', { name: /stop recording/i }));
      await user.click(screen.getByRole('button', { name: /save echo/i }));
      
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('Home');
      });
    });
  });

  describe('Error Handling', () => {
    it('handles microphone permission denial', async () => {
      const user = userEvent.setup();
      navigator.mediaDevices.getUserMedia = jest.fn().mockRejectedValue(
        new Error('Permission denied')
      );
      
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/microphone permission required/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /grant permission/i })).toBeInTheDocument();
      });
    });

    it('handles recording errors', async () => {
      const user = userEvent.setup();
      const mockMediaRecorder = {
        start: jest.fn(() => { throw new Error('Recording failed'); }),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        state: 'inactive',
      };
      
      global.MediaRecorder = jest.fn(() => mockMediaRecorder);
      
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/recording failed/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });

    it('handles save errors', async () => {
      const user = userEvent.setup();
      const mockCreateEcho = jest.fn().mockRejectedValue(new Error('Save failed'));
      
      renderRecordScreen({
        echo: {
          ...defaultContextValues.echo,
          createEcho: mockCreateEcho,
          error: 'Failed to save echo'
        }
      });
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      await user.click(screen.getByRole('button', { name: /stop recording/i }));
      await user.click(screen.getByRole('button', { name: /save echo/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/failed to save echo/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', () => {
      renderRecordScreen();
      
      expect(screen.getByRole('group', { name: /emotion selection/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /start recording/i })).toHaveAttribute('aria-describedby');
    });

    it('announces recording state changes', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      await user.click(screen.getByRole('button', { name: 'Joy' }));
      await user.click(screen.getByRole('button', { name: /start recording/i }));
      
      expect(screen.getByRole('status')).toHaveTextContent(/recording started/i);
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      renderRecordScreen();
      
      // Tab through emotion buttons
      await user.tab();
      expect(screen.getByRole('button', { name: 'Joy' })).toHaveFocus();
      
      await user.keyboard('{ArrowRight}');
      expect(screen.getByRole('button', { name: 'Calm' })).toHaveFocus();
    });
  });
});