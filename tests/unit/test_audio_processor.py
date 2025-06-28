"""
Unit tests for audio processing service
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from backend.src.services.audio_processor import (
    AudioProcessor,
    AudioProcessorConfig,
    AudioMetadata,
    AudioProcessingError,
    audio_processor
)


class TestAudioProcessor:
    """Test cases for AudioProcessor class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = AudioProcessorConfig()
        self.processor = AudioProcessor(self.config)
        
    def teardown_method(self):
        """Clean up after tests"""
        pass
    
    def test_audio_processor_initialization(self):
        """Test audio processor initialization"""
        assert self.processor.config == self.config
        assert self.processor.config.MIN_DURATION == 10.0
        assert self.processor.config.MAX_DURATION == 30.0
        assert self.processor.config.MAX_FILE_SIZE == 50 * 1024 * 1024
    
    def test_supported_formats_configuration(self):
        """Test supported audio formats configuration"""
        supported_formats = self.config.SUPPORTED_FORMATS
        
        assert 'audio/webm' in supported_formats
        assert 'audio/wav' in supported_formats
        assert 'audio/mpeg' in supported_formats
        assert '.webm' in supported_formats['audio/webm']
        assert '.wav' in supported_formats['audio/wav']
    
    def test_validate_file_upload_success(self):
        """Test successful file validation"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.flush()
            
            file_size = 1024  # 1KB
            content_type = 'audio/wav'
            
            is_valid, error_msg = self.processor.validate_file_upload(
                temp_file.name, file_size, content_type
            )
            
            assert is_valid is True
            assert error_msg == ""
    
    def test_validate_file_upload_file_too_large(self):
        """Test file validation with oversized file"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
            file_size = self.config.MAX_FILE_SIZE + 1
            content_type = 'audio/wav'
            
            is_valid, error_msg = self.processor.validate_file_upload(
                temp_file.name, file_size, content_type
            )
            
            assert is_valid is False
            assert "exceeds maximum" in error_msg
    
    def test_validate_file_upload_unsupported_format(self):
        """Test file validation with unsupported format"""
        with tempfile.NamedTemporaryFile(suffix='.xyz') as temp_file:
            file_size = 1024
            content_type = 'audio/xyz'
            
            is_valid, error_msg = self.processor.validate_file_upload(
                temp_file.name, file_size, content_type
            )
            
            assert is_valid is False
            assert "Unsupported file format" in error_msg
    
    def test_validate_file_upload_extension_mismatch(self):
        """Test file validation with mismatched extension"""
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            file_size = 1024
            content_type = 'audio/wav'  # Mismatch
            
            is_valid, error_msg = self.processor.validate_file_upload(
                temp_file.name, file_size, content_type
            )
            
            assert is_valid is False
            assert "doesn't match content type" in error_msg
    
    def test_validate_file_upload_file_not_exists(self):
        """Test file validation with non-existent file"""
        file_path = '/non/existent/file.wav'
        file_size = 1024
        content_type = 'audio/wav'
        
        is_valid, error_msg = self.processor.validate_file_upload(
            file_path, file_size, content_type
        )
        
        assert is_valid is False
        assert "does not exist" in error_msg
    
    @patch('backend.src.services.audio_processor.librosa')
    def test_extract_metadata_with_librosa(self, mock_librosa):
        """Test metadata extraction using librosa"""
        # Mock librosa.load
        mock_audio_data = np.array([0.1, 0.2, 0.3, 0.4] * 1000)  # 4000 samples
        mock_sample_rate = 44100
        mock_librosa.load.return_value = (mock_audio_data, mock_sample_rate)
        
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.flush()
            
            metadata = self.processor.extract_metadata(temp_file.name)
            
            expected_duration = len(mock_audio_data) / mock_sample_rate
            
            assert isinstance(metadata, AudioMetadata)
            assert metadata.duration == expected_duration
            assert metadata.sample_rate == mock_sample_rate
            assert metadata.channels == 1  # Mono
            assert metadata.format == '.wav'
            assert metadata.size > 0
    
    @patch('backend.src.services.audio_processor.librosa', None)
    @patch('backend.src.services.audio_processor.AudioSegment')
    def test_extract_metadata_with_pydub_fallback(self, mock_audio_segment):
        """Test metadata extraction fallback to pydub"""
        # Mock AudioSegment
        mock_audio = Mock()
        mock_audio.frame_rate = 44100
        mock_audio.channels = 2
        mock_audio.__len__ = Mock(return_value=15000)  # 15 seconds in ms
        mock_audio_segment.from_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.flush()
            
            metadata = self.processor.extract_metadata(temp_file.name)
            
            assert metadata.duration == 15.0  # 15000ms -> 15s
            assert metadata.sample_rate == 44100
            assert metadata.channels == 2
            assert metadata.valid is True  # Within 10-30s range
    
    def test_extract_metadata_duration_validation(self):
        """Test metadata extraction with duration validation"""
        with patch('backend.src.services.audio_processor.librosa') as mock_librosa:
            # Mock short audio (5 seconds - invalid)
            mock_audio_data = np.array([0.1] * 220500)  # 5 seconds at 44100 Hz
            mock_librosa.load.return_value = (mock_audio_data, 44100)
            
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
                temp_file.write(b'fake audio data')
                temp_file.flush()
                
                metadata = self.processor.extract_metadata(temp_file.name)
                
                assert metadata.valid is False
                assert "outside valid range" in metadata.error_message
    
    @patch('backend.src.services.audio_processor.librosa')
    @patch('backend.src.services.audio_processor.sf')
    def test_process_audio_file_success(self, mock_sf, mock_librosa):
        """Test audio file processing"""
        # Mock librosa operations
        mock_audio_data = np.array([0.1, 0.2] * 1000)
        mock_librosa.load.return_value = (mock_audio_data, 48000)  # Different sample rate
        mock_librosa.resample.return_value = mock_audio_data
        
        with tempfile.NamedTemporaryFile(suffix='.wav') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.wav') as output_file:
            
            input_file.write(b'fake input audio')
            input_file.flush()
            
            success = self.processor.process_audio_file(
                input_file.name, output_file.name
            )
            
            assert success is True
            mock_librosa.load.assert_called_once()
            mock_librosa.resample.assert_called_once()
            mock_sf.write.assert_called_once()
    
    @patch('backend.src.services.audio_processor.librosa', None)
    @patch('backend.src.services.audio_processor.sf', None)
    def test_process_audio_file_fallback(self):
        """Test audio processing fallback when libraries unavailable"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.wav') as output_file:
            
            input_file.write(b'fake input audio')
            input_file.flush()
            
            with patch('shutil.copy2') as mock_copy:
                success = self.processor.process_audio_file(
                    input_file.name, output_file.name
                )
                
                assert success is True
                mock_copy.assert_called_once_with(input_file.name, output_file.name)
    
    @patch('backend.src.services.audio_processor.librosa')
    def test_process_audio_file_error_handling(self, mock_librosa):
        """Test audio processing error handling"""
        mock_librosa.load.side_effect = Exception("Processing error")
        
        with tempfile.NamedTemporaryFile(suffix='.wav') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.wav') as output_file:
            
            input_file.write(b'fake input audio')
            input_file.flush()
            
            success = self.processor.process_audio_file(
                input_file.name, output_file.name
            )
            
            assert success is False
    
    def test_validate_and_process_complete_pipeline(self):
        """Test complete validation and processing pipeline"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
            temp_file.write(b'fake audio data' * 1000)
            temp_file.flush()
            
            content_type = 'audio/wav'
            
            with patch.object(self.processor, 'extract_metadata') as mock_extract, \
                 patch.object(self.processor, 'process_audio_file') as mock_process:
                
                # Mock valid metadata
                mock_metadata = AudioMetadata(
                    duration=15.0,
                    sample_rate=44100,
                    channels=2,
                    format='.wav',
                    size=1000,
                    valid=True
                )
                mock_extract.return_value = mock_metadata
                mock_process.return_value = True
                
                result = self.processor.validate_and_process(temp_file.name, content_type)
                
                assert result['success'] is True
                assert result['metadata'] == mock_metadata.dict()
                assert result['processing_applied'] is True
                assert 'processed_file' in result
    
    def test_validate_and_process_validation_failure(self):
        """Test pipeline with validation failure"""
        with tempfile.NamedTemporaryFile(suffix='.xyz') as temp_file:
            temp_file.write(b'fake data')
            temp_file.flush()
            
            content_type = 'audio/xyz'  # Unsupported
            
            result = self.processor.validate_and_process(temp_file.name, content_type)
            
            assert result['success'] is False
            assert 'Unsupported file format' in result['error']
            assert result['metadata'] is None
    
    def test_validate_and_process_invalid_audio_content(self):
        """Test pipeline with invalid audio content"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.flush()
            
            content_type = 'audio/wav'
            
            with patch.object(self.processor, 'extract_metadata') as mock_extract:
                # Mock invalid metadata (too short)
                mock_metadata = AudioMetadata(
                    duration=5.0,  # Too short
                    sample_rate=44100,
                    channels=2,
                    format='.wav',
                    size=1000,
                    valid=False,
                    error_message="Duration too short"
                )
                mock_extract.return_value = mock_metadata
                
                result = self.processor.validate_and_process(temp_file.name, content_type)
                
                assert result['success'] is False
                assert "Duration too short" in result['error']
                assert result['metadata'] == mock_metadata.dict()
    
    def test_cleanup_temp_file(self):
        """Test temporary file cleanup"""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b'test data')
            temp_path = temp_file.name
        
        # File should exist
        assert os.path.exists(temp_path)
        
        # Clean up
        self.processor.cleanup_temp_file(temp_path)
        
        # File should be removed
        assert not os.path.exists(temp_path)
    
    def test_cleanup_temp_file_not_exists(self):
        """Test cleanup of non-existent file"""
        # Should not raise exception
        self.processor.cleanup_temp_file('/non/existent/file.wav')
    
    def test_global_audio_processor_instance(self):
        """Test global audio processor instance"""
        assert audio_processor is not None
        assert isinstance(audio_processor, AudioProcessor)


class TestAudioMetadata:
    """Test cases for AudioMetadata model"""
    
    def test_audio_metadata_creation(self):
        """Test AudioMetadata model creation"""
        metadata = AudioMetadata(
            duration=15.5,
            sample_rate=44100,
            channels=2,
            format='.wav',
            size=1024000,
            valid=True
        )
        
        assert metadata.duration == 15.5
        assert metadata.sample_rate == 44100
        assert metadata.channels == 2
        assert metadata.format == '.wav'
        assert metadata.size == 1024000
        assert metadata.valid is True
        assert metadata.bitrate is None
        assert metadata.error_message is None
    
    def test_audio_metadata_with_error(self):
        """Test AudioMetadata with error message"""
        metadata = AudioMetadata(
            duration=0.0,
            sample_rate=0,
            channels=0,
            format='unknown',
            size=0,
            valid=False,
            error_message="File processing failed"
        )
        
        assert metadata.valid is False
        assert metadata.error_message == "File processing failed"
    
    def test_audio_metadata_dict_conversion(self):
        """Test AudioMetadata to dict conversion"""
        metadata = AudioMetadata(
            duration=20.0,
            sample_rate=48000,
            channels=1,
            format='.mp3',
            bitrate=128000,
            size=2048000,
            valid=True
        )
        
        metadata_dict = metadata.dict()
        
        assert metadata_dict['duration'] == 20.0
        assert metadata_dict['sample_rate'] == 48000
        assert metadata_dict['bitrate'] == 128000
        assert metadata_dict['valid'] is True


class TestAudioProcessorConfig:
    """Test cases for AudioProcessorConfig"""
    
    def test_default_configuration(self):
        """Test default configuration values"""
        config = AudioProcessorConfig()
        
        assert config.MIN_DURATION == 10.0
        assert config.MAX_DURATION == 30.0
        assert config.MAX_FILE_SIZE == 50 * 1024 * 1024
        assert config.TARGET_SAMPLE_RATE == 44100
        assert config.TARGET_CHANNELS == 2
        
        assert 'audio/webm' in config.SUPPORTED_FORMATS
        assert 'audio/wav' in config.SUPPORTED_FORMATS
        assert len(config.SUPPORTED_FORMATS) >= 4
    
    def test_supported_formats_structure(self):
        """Test supported formats structure"""
        config = AudioProcessorConfig()
        
        for mime_type, extensions in config.SUPPORTED_FORMATS.items():
            assert mime_type.startswith('audio/')
            assert isinstance(extensions, list)
            assert len(extensions) > 0
            for ext in extensions:
                assert ext.startswith('.')


@pytest.fixture
def sample_audio_file():
    """Fixture providing a sample audio file"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        # Create a minimal WAV file header + some data
        wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x44\xac\x00\x00\x01\x00\x08\x00data\x00\x08\x00\x00'
        audio_data = b'\x00' * 2000  # Silent audio data
        temp_file.write(wav_header + audio_data)
        temp_file.flush()
        yield temp_file.name
    
    # Cleanup
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)


class TestAudioProcessorIntegration:
    """Integration tests for audio processor"""
    
    def test_real_audio_file_processing(self, sample_audio_file):
        """Test processing with actual audio file structure"""
        processor = AudioProcessor()
        
        # Test validation
        file_size = os.path.getsize(sample_audio_file)
        is_valid, error_msg = processor.validate_file_upload(
            sample_audio_file, file_size, 'audio/wav'
        )
        
        assert is_valid is True
        assert error_msg == ""
        
        # Test metadata extraction (will use fallback if libraries not available)
        metadata = processor.extract_metadata(sample_audio_file)
        
        assert isinstance(metadata, AudioMetadata)
        assert metadata.format == '.wav'
        assert metadata.size == file_size
    
    @pytest.mark.skipif(
        os.getenv('SKIP_INTEGRATION_TESTS') == 'true',
        reason="Integration tests disabled"
    )
    def test_complete_processing_pipeline(self, sample_audio_file):
        """Test complete processing pipeline with real file"""
        processor = AudioProcessor()
        
        result = processor.validate_and_process(sample_audio_file, 'audio/wav')
        
        # Should succeed even if duration is invalid (for this test file)
        assert 'success' in result
        assert 'metadata' in result
        
        # Clean up any temporary files
        if result.get('processed_file'):
            processor.cleanup_temp_file(result['processed_file'])