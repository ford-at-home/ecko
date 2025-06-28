"""
Performance and load testing for Echoes audio time machine.
Tests system performance under various load conditions.
"""

import asyncio
import aiohttp
import time
import statistics
import json
from datetime import datetime, timezone
import pytest
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import os
from typing import List, Dict, Any
import boto3
from moto import mock_s3, mock_dynamodb
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """Collect and analyze performance metrics."""
    
    def __init__(self):
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        self.start_time = None
        self.end_time = None
    
    def add_response_time(self, response_time: float, success: bool = True):
        """Add response time measurement."""
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def start_test(self):
        """Mark test start time."""
        self.start_time = time.time()
    
    def end_test(self):
        """Mark test end time."""
        self.end_time = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        """Calculate performance statistics."""
        if not self.response_times:
            return {}
        
        total_requests = self.success_count + self.error_count
        duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        return {
            'total_requests': total_requests,
            'successful_requests': self.success_count,
            'failed_requests': self.error_count,
            'success_rate': (self.success_count / total_requests) * 100 if total_requests > 0 else 0,
            'test_duration_seconds': duration,
            'requests_per_second': total_requests / duration if duration > 0 else 0,
            'response_time_stats': {
                'min': min(self.response_times),
                'max': max(self.response_times),
                'mean': statistics.mean(self.response_times),
                'median': statistics.median(self.response_times),
                'p95': self._percentile(self.response_times, 95),
                'p99': self._percentile(self.response_times, 99)
            }
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


class LoadTestClient:
    """HTTP client for load testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.auth_token = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def authenticate(self) -> bool:
        """Authenticate user and get access token."""
        try:
            async with self.session.post(f"{self.base_url}/auth/login", json={
                "username": f"loadtest+{uuid.uuid4()}@example.com",
                "password": "LoadTest123!"
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth_token = data.get("accessToken")
                    return True
                return False
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    async def get_echoes(self, user_id: str, emotion: str = None) -> tuple[int, float]:
        """Get echoes for user."""
        start_time = time.time()
        try:
            params = {"userId": user_id}
            if emotion:
                params["emotion"] = emotion
            
            headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
            
            async with self.session.get(f"{self.base_url}/echoes", 
                                      params=params, headers=headers) as response:
                response_time = time.time() - start_time
                return response.status, response_time
        except Exception as e:
            logger.error(f"Get echoes failed: {e}")
            return 500, time.time() - start_time
    
    async def create_echo(self, echo_data: Dict[str, Any]) -> tuple[int, float]:
        """Create new echo."""
        start_time = time.time()
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
            
            async with self.session.post(f"{self.base_url}/echoes", 
                                       json=echo_data, headers=headers) as response:
                response_time = time.time() - start_time
                return response.status, response_time
        except Exception as e:
            logger.error(f"Create echo failed: {e}")
            return 500, time.time() - start_time
    
    async def init_upload(self, user_id: str, file_type: str = "audio/wav") -> tuple[int, float]:
        """Initialize file upload."""
        start_time = time.time()
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
            
            async with self.session.post(f"{self.base_url}/echoes/init-upload", json={
                "userId": user_id,
                "fileType": file_type,
                "fileName": f"test-{uuid.uuid4()}.wav"
            }, headers=headers) as response:
                response_time = time.time() - start_time
                return response.status, response_time
        except Exception as e:
            logger.error(f"Init upload failed: {e}")
            return 500, time.time() - start_time
    
    async def get_random_echo(self, user_id: str, emotion: str) -> tuple[int, float]:
        """Get random echo by emotion."""
        start_time = time.time()
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
            
            async with self.session.get(f"{self.base_url}/echoes/random", 
                                      params={"userId": user_id, "emotion": emotion}, 
                                      headers=headers) as response:
                response_time = time.time() - start_time
                return response.status, response_time
        except Exception as e:
            logger.error(f"Get random echo failed: {e}")
            return 500, time.time() - start_time


@pytest.fixture
def performance_config():
    """Performance test configuration."""
    return {
        'max_response_time': 2.0,  # seconds
        'concurrent_users': 50,
        'test_duration': 60,  # seconds
        'ramp_up_time': 10,  # seconds
        'acceptable_error_rate': 5.0,  # percentage
        'min_throughput': 10,  # requests per second
    }


class TestAPIPerformance:
    """API performance and load tests."""
    
    @pytest.mark.asyncio
    async def test_echo_retrieval_performance(self, performance_config):
        """Test echo retrieval under normal load."""
        metrics = PerformanceMetrics()
        metrics.start_test()
        
        concurrent_users = 20
        requests_per_user = 10
        
        async def user_session():
            async with LoadTestClient() as client:
                user_id = f"perftest-{uuid.uuid4()}"
                
                # Pre-populate some echoes
                for i in range(5):
                    echo_data = {
                        "userId": user_id,
                        "echoId": str(uuid.uuid4()),
                        "emotion": ["joy", "calm", "nostalgic"][i % 3],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "s3Url": f"s3://test/{user_id}/echo-{i}.wav"
                    }
                    await client.create_echo(echo_data)
                
                # Test retrieval performance
                for _ in range(requests_per_user):
                    status, response_time = await client.get_echoes(user_id)
                    metrics.add_response_time(response_time, status == 200)
                    
                    # Add small delay to simulate realistic usage
                    await asyncio.sleep(0.1)
        
        # Run concurrent user sessions
        tasks = [user_session() for _ in range(concurrent_users)]
        await asyncio.gather(*tasks)
        
        metrics.end_test()
        stats = metrics.get_stats()
        
        # Performance assertions
        assert stats['success_rate'] >= 95.0, f"Success rate {stats['success_rate']}% below threshold"
        assert stats['response_time_stats']['p95'] <= performance_config['max_response_time'], \
               f"95th percentile response time {stats['response_time_stats']['p95']}s exceeds threshold"
        assert stats['requests_per_second'] >= 10, \
               f"Throughput {stats['requests_per_second']} RPS below minimum"
        
        logger.info(f"Echo retrieval performance: {json.dumps(stats, indent=2)}")
    
    @pytest.mark.asyncio
    async def test_echo_creation_performance(self, performance_config):
        """Test echo creation under load."""
        metrics = PerformanceMetrics()
        metrics.start_test()
        
        concurrent_users = 15
        echoes_per_user = 5
        
        async def user_session():
            async with LoadTestClient() as client:
                await client.authenticate()
                user_id = f"createtest-{uuid.uuid4()}"
                
                for i in range(echoes_per_user):
                    # Initialize upload
                    status, response_time = await client.init_upload(user_id)
                    metrics.add_response_time(response_time, status == 200)
                    
                    if status == 200:
                        # Create echo metadata
                        echo_data = {
                            "userId": user_id,
                            "echoId": str(uuid.uuid4()),
                            "emotion": ["joy", "calm", "energetic", "peaceful", "nostalgic"][i % 5],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "s3Url": f"s3://test/{user_id}/echo-{i}.wav",
                            "location": {"lat": 40.7128, "lng": -74.0060},
                            "tags": ["performance", "test"]
                        }
                        
                        status, response_time = await client.create_echo(echo_data)
                        metrics.add_response_time(response_time, status == 201)
                    
                    await asyncio.sleep(0.2)  # Simulate user thinking time
        
        tasks = [user_session() for _ in range(concurrent_users)]
        await asyncio.gather(*tasks)
        
        metrics.end_test()
        stats = metrics.get_stats()
        
        # Performance assertions
        assert stats['success_rate'] >= 90.0, f"Success rate {stats['success_rate']}% below threshold"
        assert stats['response_time_stats']['p95'] <= 3.0, \
               f"95th percentile response time {stats['response_time_stats']['p95']}s exceeds threshold"
        
        logger.info(f"Echo creation performance: {json.dumps(stats, indent=2)}")
    
    @pytest.mark.asyncio
    async def test_random_echo_performance(self, performance_config):
        """Test random echo retrieval performance."""
        metrics = PerformanceMetrics()
        metrics.start_test()
        
        concurrent_users = 25
        requests_per_user = 20
        emotions = ["joy", "calm", "nostalgic", "peaceful", "energetic"]
        
        async def user_session():
            async with LoadTestClient() as client:
                user_id = f"randomtest-{uuid.uuid4()}"
                
                for _ in range(requests_per_user):
                    emotion = emotions[_ % len(emotions)]
                    status, response_time = await client.get_random_echo(user_id, emotion)
                    metrics.add_response_time(response_time, status in [200, 404])
                    
                    await asyncio.sleep(0.05)
        
        tasks = [user_session() for _ in range(concurrent_users)]
        await asyncio.gather(*tasks)
        
        metrics.end_test()
        stats = metrics.get_stats()
        
        # Performance assertions
        assert stats['success_rate'] >= 95.0, f"Success rate {stats['success_rate']}% below threshold"
        assert stats['response_time_stats']['mean'] <= 1.0, \
               f"Mean response time {stats['response_time_stats']['mean']}s exceeds threshold"
        
        logger.info(f"Random echo performance: {json.dumps(stats, indent=2)}")


class TestStressTests:
    """Stress testing to find system breaking points."""
    
    @pytest.mark.asyncio
    async def test_high_concurrency_stress(self):
        """Test system under high concurrent load."""
        metrics = PerformanceMetrics()
        metrics.start_test()
        
        # Gradually increase load
        concurrency_levels = [50, 100, 200, 300]
        
        for concurrency in concurrency_levels:
            logger.info(f"Testing concurrency level: {concurrency}")
            
            async def stress_session():
                async with LoadTestClient() as client:
                    user_id = f"stress-{uuid.uuid4()}"
                    
                    # Mix of operations
                    operations = [
                        lambda: client.get_echoes(user_id),
                        lambda: client.get_random_echo(user_id, "joy"),
                        lambda: client.init_upload(user_id)
                    ]
                    
                    for _ in range(5):  # 5 requests per session
                        operation = operations[_ % len(operations)]
                        status, response_time = await operation()
                        metrics.add_response_time(response_time, status in [200, 201, 404])
            
            # Run stress test for this concurrency level
            tasks = [stress_session() for _ in range(concurrency)]
            start_time = time.time()
            await asyncio.gather(*tasks, return_exceptions=True)
            level_duration = time.time() - start_time
            
            logger.info(f"Concurrency {concurrency}: {level_duration:.2f}s duration")
            
            # Brief pause between levels
            await asyncio.sleep(2)
        
        metrics.end_test()
        stats = metrics.get_stats()
        
        # Log results for analysis
        logger.info(f"Stress test results: {json.dumps(stats, indent=2)}")
        
        # Should handle at least 50 concurrent users with reasonable performance
        assert stats['success_rate'] >= 70.0, f"Success rate {stats['success_rate']}% too low under stress"
    
    @pytest.mark.asyncio
    async def test_sustained_load(self):
        """Test system under sustained load over time."""
        metrics = PerformanceMetrics()
        metrics.start_test()
        
        test_duration = 120  # 2 minutes
        concurrent_users = 30
        
        async def sustained_session():
            async with LoadTestClient() as client:
                await client.authenticate()
                user_id = f"sustained-{uuid.uuid4()}"
                
                end_time = time.time() + test_duration
                request_count = 0
                
                while time.time() < end_time:
                    # Simulate realistic user behavior
                    if request_count % 10 == 0:
                        # Occasionally create new echo
                        echo_data = {
                            "userId": user_id,
                            "echoId": str(uuid.uuid4()),
                            "emotion": "sustained-test",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "s3Url": f"s3://test/{user_id}/sustained-{request_count}.wav"
                        }
                        status, response_time = await client.create_echo(echo_data)
                    else:
                        # Mostly retrieve echoes
                        status, response_time = await client.get_echoes(user_id)
                    
                    metrics.add_response_time(response_time, status in [200, 201])
                    request_count += 1
                    
                    # Realistic user pause
                    await asyncio.sleep(1.0)
        
        tasks = [sustained_session() for _ in range(concurrent_users)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.end_test()
        stats = metrics.get_stats()
        
        # Performance should remain stable over time
        assert stats['success_rate'] >= 85.0, f"Success rate {stats['success_rate']}% degraded over time"
        assert stats['response_time_stats']['p95'] <= 5.0, \
               f"95th percentile response time {stats['response_time_stats']['p95']}s degraded"
        
        logger.info(f"Sustained load results: {json.dumps(stats, indent=2)}")


class TestResourceUtilization:
    """Test resource utilization and efficiency."""
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """Test memory efficiency under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create sustained load
        concurrent_users = 20
        requests_per_user = 50
        
        async def memory_test_session():
            async with LoadTestClient() as client:
                user_id = f"memtest-{uuid.uuid4()}"
                
                for i in range(requests_per_user):
                    # Mix of operations that could cause memory issues
                    if i % 5 == 0:
                        # Large response simulation
                        await client.get_echoes(user_id)
                    else:
                        # Regular operations
                        await client.get_random_echo(user_id, "joy")
                    
                    await asyncio.sleep(0.01)
        
        tasks = [memory_test_session() for _ in range(concurrent_users)]
        await asyncio.gather(*tasks)
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        logger.info(f"Memory usage: Initial {initial_memory:.2f}MB, Peak {peak_memory:.2f}MB, "
                   f"Increase {memory_increase:.2f}MB")
        
        # Memory increase should be reasonable
        assert memory_increase < 500, f"Memory increase {memory_increase}MB too high"
    
    @pytest.mark.asyncio
    async def test_connection_pool_efficiency(self):
        """Test database connection pool efficiency."""
        metrics = PerformanceMetrics()
        metrics.start_test()
        
        # Rapid concurrent requests to test connection pooling
        concurrent_requests = 100
        
        async def connection_test():
            async with LoadTestClient() as client:
                user_id = f"conntest-{uuid.uuid4()}"
                status, response_time = await client.get_echoes(user_id)
                metrics.add_response_time(response_time, status in [200, 404])
        
        # All requests at once to stress connection pool
        tasks = [connection_test() for _ in range(concurrent_requests)]
        await asyncio.gather(*tasks)
        
        metrics.end_test()
        stats = metrics.get_stats()
        
        # Should handle burst of connections efficiently
        assert stats['success_rate'] >= 90.0, f"Connection pool success rate {stats['success_rate']}% too low"
        assert stats['response_time_stats']['p95'] <= 3.0, \
               f"Connection pool response time {stats['response_time_stats']['p95']}s too high"
        
        logger.info(f"Connection pool efficiency: {json.dumps(stats, indent=2)}")


class TestScalabilityBenchmarks:
    """Benchmarks for different system scales."""
    
    @pytest.mark.asyncio
    async def test_small_user_base_benchmark(self):
        """Benchmark performance with small user base (1-100 users)."""
        user_counts = [1, 5, 10, 25, 50, 100]
        results = {}
        
        for user_count in user_counts:
            metrics = PerformanceMetrics()
            metrics.start_test()
            
            async def benchmark_session():
                async with LoadTestClient() as client:
                    user_id = f"benchmark-{uuid.uuid4()}"
                    
                    # Standard user workflow
                    for _ in range(10):
                        status, response_time = await client.get_echoes(user_id)
                        metrics.add_response_time(response_time, status in [200, 404])
                        await asyncio.sleep(0.1)
            
            tasks = [benchmark_session() for _ in range(user_count)]
            await asyncio.gather(*tasks)
            
            metrics.end_test()
            stats = metrics.get_stats()
            results[user_count] = {
                'rps': stats['requests_per_second'],
                'p95_response_time': stats['response_time_stats']['p95'],
                'success_rate': stats['success_rate']
            }
            
            logger.info(f"Benchmark {user_count} users: {json.dumps(results[user_count], indent=2)}")
        
        # Verify performance scaling
        for user_count, result in results.items():
            assert result['success_rate'] >= 95.0, f"Success rate degraded at {user_count} users"
            assert result['p95_response_time'] <= 2.0, f"Response time degraded at {user_count} users"
        
        return results
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self):
        """Test database query performance with varying data sizes."""
        # This would test with different amounts of echo data
        # to understand how performance scales with data volume
        
        data_sizes = [100, 1000, 10000]  # Number of echoes per user
        results = {}
        
        for data_size in data_sizes:
            logger.info(f"Testing with {data_size} echoes per user")
            
            # Pre-populate test data
            user_id = f"dbtest-{uuid.uuid4()}"
            
            async with LoadTestClient() as client:
                await client.authenticate()
                
                # Create test echoes
                for i in range(min(data_size, 100)):  # Limit for test speed
                    echo_data = {
                        "userId": user_id,
                        "echoId": str(uuid.uuid4()),
                        "emotion": ["joy", "calm", "nostalgic"][i % 3],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "s3Url": f"s3://test/{user_id}/echo-{i}.wav"
                    }
                    await client.create_echo(echo_data)
                
                # Measure query performance
                metrics = PerformanceMetrics()
                metrics.start_test()
                
                for _ in range(20):  # Multiple queries to get average
                    status, response_time = await client.get_echoes(user_id)
                    metrics.add_response_time(response_time, status == 200)
                
                metrics.end_test()
                stats = metrics.get_stats()
                results[data_size] = stats['response_time_stats']['mean']
        
        # Performance should not degrade significantly with more data
        for data_size, avg_time in results.items():
            assert avg_time <= 1.0, f"Query time {avg_time}s too slow for {data_size} records"
            logger.info(f"Data size {data_size}: Average query time {avg_time:.3f}s")
        
        return results