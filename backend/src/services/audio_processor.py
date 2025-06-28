"""
Audio Processing Service for Echoes App
Handles audio file validation, processing, and metadata extraction
"""

import os
import tempfile
import logging
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import mimetypes

try:
    import librosa
    import soundfile as sf
    from pydub import AudioSegment
    from mutagen import File as MutagenFile
    import numpy as np
except ImportError as e:
    logging.warning(f"Audio processing library not available: {e}")
    librosa = None
    sf = None
    AudioSegment = None
    MutagenFile = None
    np = None

from pydantic import BaseModel


class AudioMetadata(BaseModel):
    """Audio file metadata model"""
    duration: float
    sample_rate: int
    channels: int
    format: str
    bitrate: Optional[int] = None
    size: int
    valid: bool
    error_message: Optional[str] = None


class AudioProcessorConfig:
    """Configuration for audio processing"""
    MIN_DURATION = 10.0  # seconds
    MAX_DURATION = 30.0  # seconds
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    SUPPORTED_FORMATS = {
        'audio/webm': ['.webm'],
        'audio/wav': ['.wav'],
        'audio/mpeg': ['.mp3'],
        'audio/ogg': ['.ogg'],
        'audio/x-m4a': ['.m4a'],
        'audio/mp4': ['.mp4']
    }
    TARGET_SAMPLE_RATE = 44100
    TARGET_CHANNELS = 2  # stereo


class AudioProcessingError(Exception):
    """Custom exception for audio processing errors"""
    pass


class AudioProcessor:
    """
    Main audio processing service
    Handles validation, processing, and metadata extraction
    """
    
    def __init__(self, config: Optional[AudioProcessorConfig] = None):
        self.config = config or AudioProcessorConfig()
        self.logger = logging.getLogger(__name__)
    
    def validate_file_upload(self, file_path: str, file_size: int, content_type: str) -> Tuple[bool, str]:
        """
        Validate uploaded audio file before processing
        
        Args:
            file_path: Path to the uploaded file
            file_size: Size of the file in bytes
            content_type: MIME type of the file
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file size
            if file_size > self.config.MAX_FILE_SIZE:
                return False, f"File size {file_size} exceeds maximum {self.config.MAX_FILE_SIZE} bytes"
            
            # Check content type
            if content_type not in self.config.SUPPORTED_FORMATS:
                return False, f"Unsupported file format: {content_type}"
            
            # Check file extension
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in self.config.SUPPORTED_FORMATS[content_type]:
                return False, f"File extension {file_ext} doesn't match content type {content_type}"
            
            # Validate file exists and is readable
            if not os.path.exists(file_path):
                return False, "File does not exist"
            
            if not os.access(file_path, os.R_OK):
                return False, "File is not readable"
            
            return True, ""
            
        except Exception as e:
            self.logger.error(f"Error validating file: {e}")
            return False, f"Validation error: {str(e)}"
    
    def extract_metadata(self, file_path: str) -> AudioMetadata:
        """
        Extract metadata from audio file
        
        Args:
            file_path: Path to the audio file
        
        Returns:
            AudioMetadata object with file information
        """
        try:
            # Get file size
            file_size = os.path.getsize(file_path)
            file_ext = Path(file_path).suffix.lower()
            
            # Try to load with librosa for detailed analysis
            if librosa is not None:
                try:
                    # Load audio file
                    audio_data, sample_rate = librosa.load(file_path, sr=None)
                    duration = len(audio_data) / sample_rate
                    
                    # Detect channels
                    if len(audio_data.shape) > 1:
                        channels = audio_data.shape[1]
                    else:
                        channels = 1
                    
                    # Try to get additional metadata with mutagen
                    bitrate = None
                    if MutagenFile is not None:
                        try:
                            mutagen_file = MutagenFile(file_path)
                            if mutagen_file is not None and hasattr(mutagen_file, 'info'):
                                bitrate = getattr(mutagen_file.info, 'bitrate', None)
                        except Exception:
                            pass
                    
                    # Validate duration
                    valid = self.config.MIN_DURATION <= duration <= self.config.MAX_DURATION
                    error_message = None
                    if not valid:
                        error_message = f"Duration {duration:.2f}s outside valid range {self.config.MIN_DURATION}-{self.config.MAX_DURATION}s"
                    
                    return AudioMetadata(
                        duration=duration,
                        sample_rate=sample_rate,
                        channels=channels,
                        format=file_ext,
                        bitrate=bitrate,
                        size=file_size,
                        valid=valid,
                        error_message=error_message
                    )
                    
                except Exception as e:
                    self.logger.error(f"Error processing with librosa: {e}")
            
            # Fallback to pydub
            if AudioSegment is not None:
                try:
                    audio = AudioSegment.from_file(file_path)
                    duration = len(audio) / 1000.0  # Convert ms to seconds
                    sample_rate = audio.frame_rate
                    channels = audio.channels
                    
                    # Validate duration
                    valid = self.config.MIN_DURATION <= duration <= self.config.MAX_DURATION
                    error_message = None
                    if not valid:
                        error_message = f"Duration {duration:.2f}s outside valid range {self.config.MIN_DURATION}-{self.config.MAX_DURATION}s"
                    
                    return AudioMetadata(
                        duration=duration,
                        sample_rate=sample_rate,
                        channels=channels,
                        format=file_ext,
                        size=file_size,
                        valid=valid,
                        error_message=error_message
                    )
                    
                except Exception as e:
                    self.logger.error(f"Error processing with pydub: {e}")
            
            # If all else fails, return basic metadata
            return AudioMetadata(
                duration=0.0,
                sample_rate=0,
                channels=0,
                format=file_ext,
                size=file_size,
                valid=False,
                error_message="Unable to process audio file - missing audio libraries"
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            return AudioMetadata(
                duration=0.0,
                sample_rate=0,
                channels=0,
                format="unknown",
                size=0,
                valid=False,
                error_message=f"Metadata extraction error: {str(e)}"
            )
    
    def process_audio_file(self, input_path: str, output_path: str) -> bool:
        """
        Process audio file for standardization
        Normalizes sample rate, channels, and format
        
        Args:
            input_path: Path to input audio file
            output_path: Path for processed output file
        
        Returns:
            Success status
        """
        try:
            if librosa is None or sf is None:
                self.logger.warning("Audio processing libraries not available, copying file as-is")
                import shutil
                shutil.copy2(input_path, output_path)
                return True
            
            # Load audio with librosa
            audio_data, original_sr = librosa.load(input_path, sr=None)
            
            # Resample if needed
            if original_sr != self.config.TARGET_SAMPLE_RATE:
                audio_data = librosa.resample(
                    audio_data, 
                    orig_sr=original_sr, 
                    target_sr=self.config.TARGET_SAMPLE_RATE
                )
            
            # Convert to stereo if needed
            if len(audio_data.shape) == 1 and self.config.TARGET_CHANNELS == 2:
                # Convert mono to stereo by duplicating channel
                audio_data = np.stack([audio_data, audio_data], axis=0)
            elif len(audio_data.shape) == 2 and self.config.TARGET_CHANNELS == 1:
                # Convert stereo to mono by averaging channels
                audio_data = np.mean(audio_data, axis=0)
            
            # Normalize audio levels
            if np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data)) * 0.95
            
            # Save processed audio
            sf.write(output_path, audio_data.T, self.config.TARGET_SAMPLE_RATE)
            
            self.logger.info(f"Successfully processed audio: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing audio file: {e}")
            return False
    
    def validate_and_process(self, file_path: str, content_type: str) -> Dict[str, Any]:
        """
        Complete validation and processing pipeline
        
        Args:
            file_path: Path to the uploaded file
            content_type: MIME type of the file
        
        Returns:
            Processing result with metadata and status
        """
        try:
            file_size = os.path.getsize(file_path)
            
            # Validate file
            is_valid, validation_error = self.validate_file_upload(file_path, file_size, content_type)
            if not is_valid:
                return {
                    "success": False,
                    "error": validation_error,
                    "metadata": None
                }
            
            # Extract metadata
            metadata = self.extract_metadata(file_path)
            
            # Check if audio content is valid
            if not metadata.valid:
                return {
                    "success": False,
                    "error": metadata.error_message,
                    "metadata": metadata.dict()
                }
            
            # Create processed version if needed
            processed_path = None
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                processed_path = temp_file.name
            
            processing_success = self.process_audio_file(file_path, processed_path)
            
            result = {
                "success": True,
                "metadata": metadata.dict(),
                "processed_file": processed_path if processing_success else None,
                "processing_applied": processing_success
            }
            
            self.logger.info(f"Audio validation and processing completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Error in validation and processing pipeline: {e}")
            return {
                "success": False,
                "error": f"Processing pipeline error: {str(e)}",
                "metadata": None
            }
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """Clean up temporary files"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            self.logger.error(f"Error cleaning up temp file {file_path}: {e}")


# Global processor instance
audio_processor = AudioProcessor()