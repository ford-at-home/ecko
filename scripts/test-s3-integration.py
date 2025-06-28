#!/usr/bin/env python3

"""
S3 Integration Testing Script for Echoes Audio Storage
Tests presigned URL generation, file upload, and cleanup functionality
"""

import requests
import json
import sys
import os
import tempfile
import time
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class S3IntegrationTester:
    """Comprehensive S3 integration testing suite"""
    
    def __init__(self, api_base_url: str, auth_token: str):
        """
        Initialize tester
        
        Args:
            api_base_url: Base URL for the API (e.g., http://localhost:8000)
            auth_token: JWT authentication token
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json'
        }
        self.test_results = []
        
    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "PASS" if success else "FAIL"
        logger.info(f"[{status}] {test_name}: {details}")
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def create_test_audio_file(self, duration_seconds: int = 5) -> str:
        """Create a temporary test audio file"""
        try:
            # Create a simple test audio file (WebM format simulation)
            test_data = b'\x1a\x45\xdf\xa3' + b'\x00' * 1024  # Simple WebM header + padding
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
            temp_file.write(test_data)
            temp_file.close()
            
            logger.info(f"Created test audio file: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Failed to create test audio file: {e}")
            raise
    
    def test_presigned_url_generation(self) -> Optional[Dict[str, Any]]:
        """Test presigned URL generation for both endpoints"""
        try:
            # Test new endpoint
            test_data = {
                "file_extension": "webm",
                "content_type": "audio/webm"
            }
            
            response = requests.post(
                f"{self.api_base_url}/echoes/upload-url",
                headers=self.headers,
                json=test_data
            )
            
            if response.status_code == 201:
                data = response.json()
                required_fields = ['upload_url', 'echo_id', 's3_key', 'expires_in']
                
                if all(field in data for field in required_fields):
                    self.log_test_result(
                        "Presigned URL Generation (/upload-url)",
                        True,
                        f"Generated URL for echo {data['echo_id']}"
                    )
                    return data
                else:
                    self.log_test_result(
                        "Presigned URL Generation (/upload-url)",
                        False,
                        f"Missing required fields in response: {data}"
                    )
            else:
                self.log_test_result(
                    "Presigned URL Generation (/upload-url)",
                    False,
                    f"HTTP {response.status_code}: {response.text}"
                )
            
            # Test legacy endpoint
            response = requests.post(
                f"{self.api_base_url}/echoes/init-upload",
                headers=self.headers,
                json=test_data
            )
            
            if response.status_code == 201:
                self.log_test_result(
                    "Presigned URL Generation (/init-upload)",
                    True,
                    "Legacy endpoint working"
                )
            else:
                self.log_test_result(
                    "Presigned URL Generation (/init-upload)",
                    False,
                    f"HTTP {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            self.log_test_result(
                "Presigned URL Generation",
                False,
                f"Exception: {str(e)}"
            )
            
        return None
    
    def test_file_upload(self, presigned_data: Dict[str, Any]) -> bool:
        """Test actual file upload to S3"""
        try:
            # Create test file
            test_file_path = self.create_test_audio_file()
            
            try:
                # Upload file using presigned URL
                with open(test_file_path, 'rb') as f:
                    files = {'file': f}
                    
                    # For presigned POST, we need to send the data as form fields
                    upload_url = presigned_data['upload_url']
                    
                    # Simple PUT upload test
                    response = requests.put(
                        upload_url,
                        data=f.read(),
                        headers={'Content-Type': 'audio/webm'}
                    )
                
                if response.status_code in [200, 204]:
                    self.log_test_result(
                        "File Upload to S3",
                        True,
                        f"Uploaded file with key: {presigned_data['s3_key']}"
                    )
                    return True
                else:
                    self.log_test_result(
                        "File Upload to S3",
                        False,
                        f"HTTP {response.status_code}: {response.text}"
                    )
                    
            finally:
                # Clean up test file
                os.unlink(test_file_path)
                
        except Exception as e:
            self.log_test_result(
                "File Upload to S3",
                False,
                f"Exception: {str(e)}"
            )
            
        return False
    
    def test_echo_creation(self, echo_id: str) -> Optional[Dict[str, Any]]:
        """Test echo metadata creation"""
        try:
            echo_data = {
                "emotion": "joy",
                "tags": ["test", "automated"],
                "transcript": "This is a test audio file",
                "detected_mood": "happy",
                "file_extension": "webm",
                "duration_seconds": 5.0,
                "location": {
                    "lat": 37.7749,
                    "lng": -122.4194,
                    "address": "San Francisco, CA"
                }
            }
            
            response = requests.post(
                f"{self.api_base_url}/echoes?echo_id={echo_id}",
                headers=self.headers,
                json=echo_data
            )
            
            if response.status_code == 201:
                data = response.json()
                self.log_test_result(
                    "Echo Creation",
                    True,
                    f"Created echo with ID: {data.get('echo_id')}"
                )
                return data
            else:
                self.log_test_result(
                    "Echo Creation",
                    False,
                    f"HTTP {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            self.log_test_result(
                "Echo Creation",
                False,
                f"Exception: {str(e)}"
            )
            
        return None
    
    def test_echo_retrieval(self, echo_id: str) -> bool:
        """Test echo retrieval"""
        try:
            response = requests.get(
                f"{self.api_base_url}/echoes/{echo_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test_result(
                    "Echo Retrieval",
                    True,
                    f"Retrieved echo: {data.get('echo_id')}"
                )
                return True
            else:
                self.log_test_result(
                    "Echo Retrieval",
                    False,
                    f"HTTP {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            self.log_test_result(
                "Echo Retrieval",
                False,
                f"Exception: {str(e)}"
            )
            
        return False
    
    def test_echo_deletion(self, echo_id: str) -> bool:
        """Test echo deletion (including S3 file cleanup)"""
        try:
            response = requests.delete(
                f"{self.api_base_url}/echoes/{echo_id}",
                headers=self.headers
            )
            
            if response.status_code == 204:
                self.log_test_result(
                    "Echo Deletion",
                    True,
                    f"Deleted echo and S3 file: {echo_id}"
                )
                return True
            else:
                self.log_test_result(
                    "Echo Deletion",
                    False,
                    f"HTTP {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            self.log_test_result(
                "Echo Deletion",
                False,
                f"Exception: {str(e)}"
            )
            
        return False
    
    def test_validation_errors(self) -> None:
        """Test various validation scenarios"""
        test_cases = [
            {
                "name": "Invalid file extension",
                "data": {"file_extension": "txt", "content_type": "text/plain"},
                "expected_status": 400
            },
            {
                "name": "Mismatched content type",
                "data": {"file_extension": "webm", "content_type": "audio/mp3"},
                "expected_status": 400
            },
            {
                "name": "Missing file extension",
                "data": {"content_type": "audio/webm"},
                "expected_status": 422
            }
        ]
        
        for test_case in test_cases:
            try:
                response = requests.post(
                    f"{self.api_base_url}/echoes/upload-url",
                    headers=self.headers,
                    json=test_case["data"]
                )
                
                success = response.status_code == test_case["expected_status"]
                self.log_test_result(
                    f"Validation: {test_case['name']}",
                    success,
                    f"Expected {test_case['expected_status']}, got {response.status_code}"
                )
                
            except Exception as e:
                self.log_test_result(
                    f"Validation: {test_case['name']}",
                    False,
                    f"Exception: {str(e)}"
                )
    
    def test_api_health(self) -> bool:
        """Test API health endpoint"""
        try:
            response = requests.get(f"{self.api_base_url}/echoes/health")
            
            if response.status_code == 200:
                self.log_test_result(
                    "API Health Check",
                    True,
                    "API is responsive"
                )
                return True
            else:
                self.log_test_result(
                    "API Health Check",
                    False,
                    f"HTTP {response.status_code}"
                )
                
        except Exception as e:
            self.log_test_result(
                "API Health Check",
                False,
                f"Exception: {str(e)}"
            )
            
        return False
    
    def run_full_test_suite(self) -> Dict[str, Any]:
        """Run the complete test suite"""
        logger.info("Starting S3 integration test suite...")
        start_time = time.time()
        
        # Test API health first
        if not self.test_api_health():
            logger.error("API health check failed. Stopping tests.")
            return self.generate_report(start_time)
        
        # Test validation
        self.test_validation_errors()
        
        # Test presigned URL generation
        presigned_data = self.test_presigned_url_generation()
        if not presigned_data:
            logger.error("Presigned URL generation failed. Skipping upload tests.")
            return self.generate_report(start_time)
        
        # Test file upload
        upload_success = self.test_file_upload(presigned_data)
        
        # Test echo creation
        echo_data = self.test_echo_creation(presigned_data['echo_id'])
        
        # Test echo retrieval
        if echo_data:
            self.test_echo_retrieval(echo_data['echo_id'])
        
        # Test echo deletion (cleanup)
        if echo_data:
            self.test_echo_deletion(echo_data['echo_id'])
        
        return self.generate_report(start_time)
    
    def generate_report(self, start_time: float) -> Dict[str, Any]:
        """Generate test report"""
        end_time = time.time()
        duration = end_time - start_time
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                'duration_seconds': round(duration, 2)
            },
            'results': self.test_results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Test suite completed in {duration:.2f} seconds")
        logger.info(f"Results: {passed_tests}/{total_tests} tests passed ({report['summary']['success_rate']:.1f}%)")
        
        return report


def main():
    """Main function"""
    if len(sys.argv) < 3:
        print("Usage: python3 test-s3-integration.py <api_base_url> <auth_token>")
        print("Example: python3 test-s3-integration.py http://localhost:8000 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        sys.exit(1)
    
    api_base_url = sys.argv[1]
    auth_token = sys.argv[2]
    
    # Optional: Save report to file
    save_report = len(sys.argv) > 3 and sys.argv[3].lower() == '--save'
    
    tester = S3IntegrationTester(api_base_url, auth_token)
    report = tester.run_full_test_suite()
    
    # Print summary
    print("\n" + "="*60)
    print("S3 INTEGRATION TEST REPORT")
    print("="*60)
    print(f"Total Tests: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
    print(f"Duration: {report['summary']['duration_seconds']}s")
    
    if save_report:
        report_file = f"s3-test-report-{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Detailed report saved to: {report_file}")
    
    # Exit with error code if tests failed
    if report['summary']['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()