"""
Audio file cleanup service for managing S3 storage lifecycle
Handles automated cleanup of old/orphaned audio files
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.services.s3 import S3AudioService
from app.services.dynamodb_service import dynamodb_service

logger = logging.getLogger(__name__)


class AudioCleanupService:
    """Service for cleaning up audio files and managing storage lifecycle"""
    
    def __init__(self, s3_service: S3AudioService, max_workers: int = 4):
        """
        Initialize cleanup service
        
        Args:
            s3_service: S3 service instance
            max_workers: Maximum number of concurrent cleanup workers
        """
        self.s3_service = s3_service
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    async def cleanup_orphaned_files(self, user_id: str = None) -> Dict[str, Any]:
        """
        Clean up audio files that exist in S3 but not in DynamoDB
        
        Args:
            user_id: Optional user ID to limit cleanup scope
            
        Returns:
            Cleanup statistics
        """
        try:
            logger.info(f"Starting orphaned files cleanup for user: {user_id or 'all users'}")
            
            if user_id:
                # Clean up for specific user
                stats = await self._cleanup_user_orphaned_files(user_id)
            else:
                # Clean up for all users (admin operation)
                stats = await self._cleanup_all_orphaned_files()
            
            logger.info(f"Orphaned files cleanup completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during orphaned files cleanup: {e}")
            return {"error": str(e), "files_deleted": 0}
    
    async def cleanup_old_files(
        self,
        user_id: str,
        older_than_days: int = 365
    ) -> Dict[str, Any]:
        """
        Clean up old files for a user
        
        Args:
            user_id: User identifier
            older_than_days: Delete files older than this many days
            
        Returns:
            Cleanup statistics
        """
        try:
            logger.info(f"Cleaning up files older than {older_than_days} days for user {user_id}")
            
            # Run cleanup in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            deleted_count = await loop.run_in_executor(
                self.executor,
                self.s3_service.cleanup_user_files,
                user_id,
                older_than_days
            )
            
            stats = {
                "user_id": user_id,
                "files_deleted": deleted_count,
                "older_than_days": older_than_days,
                "cleanup_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Old files cleanup completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during old files cleanup: {e}")
            return {"error": str(e), "files_deleted": 0}
    
    async def _cleanup_user_orphaned_files(self, user_id: str) -> Dict[str, Any]:
        """Clean up orphaned files for a specific user"""
        try:
            # Get all S3 files for user
            s3_files = set()
            
            # List S3 objects with user prefix
            loop = asyncio.get_event_loop()
            paginator = self.s3_service.s3_client.get_paginator('list_objects_v2')
            
            async def list_s3_files():
                files = set()
                for page in paginator.paginate(
                    Bucket=self.s3_service.bucket_name,
                    Prefix=f"{user_id}/"
                ):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            files.add(obj['Key'])
                return files
            
            s3_files = await loop.run_in_executor(self.executor, lambda: asyncio.run(list_s3_files()))
            
            # Get all echo S3 keys from DynamoDB
            db_files = set()
            echoes, _ = dynamodb_service.list_echoes(user_id=user_id, limit=1000)
            
            for echo in echoes:
                if echo.s3_key:
                    db_files.add(echo.s3_key)
            
            # Find orphaned files (in S3 but not in DB)
            orphaned_files = s3_files - db_files
            
            # Delete orphaned files
            deleted_count = 0
            for s3_key in orphaned_files:
                try:
                    success = await loop.run_in_executor(
                        self.executor,
                        self.s3_service.delete_file,
                        s3_key
                    )
                    if success:
                        deleted_count += 1
                        logger.info(f"Deleted orphaned file: {s3_key}")
                except Exception as e:
                    logger.warning(f"Failed to delete orphaned file {s3_key}: {e}")
            
            return {
                "user_id": user_id,
                "s3_files_found": len(s3_files),
                "db_files_found": len(db_files),
                "orphaned_files_found": len(orphaned_files),
                "files_deleted": deleted_count,
                "cleanup_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up orphaned files for user {user_id}: {e}")
            raise
    
    async def _cleanup_all_orphaned_files(self) -> Dict[str, Any]:
        """Clean up orphaned files for all users (admin operation)"""
        try:
            # This is a more complex operation that would require
            # iterating through all users and their files
            # For now, return a placeholder
            logger.warning("Global orphaned files cleanup not implemented")
            return {
                "message": "Global cleanup not implemented",
                "files_deleted": 0
            }
            
        except Exception as e:
            logger.error(f"Error during global orphaned files cleanup: {e}")
            raise
    
    async def get_storage_report(self, user_id: str) -> Dict[str, Any]:
        """
        Generate storage usage report for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            Storage usage report
        """
        try:
            logger.info(f"Generating storage report for user {user_id}")
            
            # Get storage stats from S3
            loop = asyncio.get_event_loop()
            s3_stats = await loop.run_in_executor(
                self.executor,
                self.s3_service.get_user_storage_stats,
                user_id
            )
            
            # Get echo count from DynamoDB
            echoes, _ = dynamodb_service.list_echoes(user_id=user_id, limit=1000)
            db_echo_count = len(echoes)
            
            # Calculate potential savings from cleanup
            cutoff_date = datetime.utcnow() - timedelta(days=365)
            old_echoes = [e for e in echoes if e.created_at.replace(tzinfo=None) < cutoff_date]
            
            report = {
                "user_id": user_id,
                "s3_storage": s3_stats,
                "db_echo_count": db_echo_count,
                "old_echoes_count": len(old_echoes),
                "potential_cleanup_savings": {
                    "files": len(old_echoes),
                    "estimated_size_mb": len(old_echoes) * 2  # Estimated 2MB per file
                },
                "report_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Storage report generated: {report}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating storage report: {e}")
            return {"error": str(e)}
    
    async def verify_file_integrity(self, user_id: str) -> Dict[str, Any]:
        """
        Verify file integrity between S3 and DynamoDB
        
        Args:
            user_id: User identifier
            
        Returns:
            Integrity verification report
        """
        try:
            logger.info(f"Verifying file integrity for user {user_id}")
            
            # Get echoes from DynamoDB
            echoes, _ = dynamodb_service.list_echoes(user_id=user_id, limit=1000)
            
            missing_files = []
            verified_files = []
            errors = []
            
            # Check each echo's S3 file
            for echo in echoes:
                try:
                    loop = asyncio.get_event_loop()
                    exists = await loop.run_in_executor(
                        self.executor,
                        self.s3_service.check_file_exists,
                        echo.s3_key
                    )
                    
                    if exists:
                        verified_files.append(echo.s3_key)
                    else:
                        missing_files.append({
                            "echo_id": echo.echo_id,
                            "s3_key": echo.s3_key,
                            "created_at": echo.created_at.isoformat()
                        })
                        
                except Exception as e:
                    errors.append({
                        "echo_id": echo.echo_id,
                        "s3_key": echo.s3_key,
                        "error": str(e)
                    })
            
            report = {
                "user_id": user_id,
                "total_echoes": len(echoes),
                "verified_files": len(verified_files),
                "missing_files": len(missing_files),
                "errors": len(errors),
                "missing_files_details": missing_files,
                "errors_details": errors,
                "verification_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"File integrity verification completed: {report}")
            return report
            
        except Exception as e:
            logger.error(f"Error during file integrity verification: {e}")
            return {"error": str(e)}
    
    def __del__(self):
        """Cleanup executor on service destruction"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)


def create_cleanup_service(s3_service: S3AudioService) -> AudioCleanupService:
    """
    Factory function to create cleanup service
    
    Args:
        s3_service: S3 service instance
        
    Returns:
        AudioCleanupService instance
    """
    return AudioCleanupService(s3_service)