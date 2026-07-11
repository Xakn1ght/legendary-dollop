"""
Health check utilities for ASSTRO bot
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AsyncSessionLocal
from app.services.pasarguard import pasarguard_api
from app.utils.logger import bot_logger, log_error


class HealthChecker:
    """System health checker"""
    
    def __init__(self):
        self.last_check = None
        self.health_status = {}
        self.error_count = 0
        self.start_time = datetime.now()
    
    async def check_database_connection(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        start_time = time.time()
        try:
            async with AsyncSessionLocal() as session:
                # Test basic query
                result = await session.execute(text("SELECT 1"))
                result.fetchone()
                
                # Test user count query
                from sqlalchemy.future import select

                from app.database.models import User
                user_result = await session.execute(select(User))
                user_count = len(user_result.scalars().all())
                
                duration = time.time() - start_time
                
                return {
                    "status": "healthy",
                    "response_time_ms": round(duration * 1000, 2),
                    "user_count": user_count,
                    "error": None
                }
                
        except Exception as e:
            duration = time.time() - start_time
            log_error(e, {"operation": "health_check_database"})
            return {
                "status": "unhealthy",
                "response_time_ms": round(duration * 1000, 2),
                "user_count": None,
                "error": str(e)
            }
    
    async def check_pasarguard_connection(self) -> Dict[str, Any]:
        """Check PasarGuard API connectivity"""
        start_time = time.time()
        try:
            # Test login
            login_success = await pasarguard_api._login()
            duration = time.time() - start_time
            
            if login_success:
                return {
                    "status": "healthy",
                    "response_time_ms": round(duration * 1000, 2),
                    "error": None
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time_ms": round(duration * 1000, 2),
                    "error": "Login failed"
                }
                
        except Exception as e:
            duration = time.time() - start_time
            log_error(e, {"operation": "health_check_pasarguard"})
            return {
                "status": "unhealthy",
                "response_time_ms": round(duration * 1000, 2),
                "error": str(e)
            }
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "status": "healthy",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "error": None
            }
            
        except ImportError:
            return {
                "status": "unknown",
                "error": "psutil not available"
            }
        except Exception as e:
            log_error(e, {"operation": "health_check_resources"})
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_bot_status(self) -> Dict[str, Any]:
        """Check bot operational status"""
        uptime = datetime.now() - self.start_time
        
        return {
            "status": "healthy",
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_formatted": str(uptime).split('.')[0],
            "error_count": self.error_count,
            "last_check": self.last_check.isoformat() if self.last_check else None
        }
    
    async def run_full_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        self.last_check = datetime.now()
        
        # Run all checks concurrently
        tasks = [
            self.check_database_connection(),
            self.check_pasarguard_connection(),
            self.check_system_resources(),
            self.check_bot_status()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        health_status = {
            "database": results[0] if not isinstance(results[0], Exception) else {
                "status": "unhealthy",
                "error": str(results[0])
            },
            "pasarguard": results[1] if not isinstance(results[1], Exception) else {
                "status": "unhealthy",
                "error": str(results[1])
            },
            "system": results[2] if not isinstance(results[2], Exception) else {
                "status": "unhealthy",
                "error": str(results[2])
            },
            "bot": results[3] if not isinstance(results[3], Exception) else {
                "status": "unhealthy",
                "error": str(results[3])
            },
            "timestamp": self.last_check.isoformat()
        }
        
        # Determine overall status
        all_healthy = all(
            component.get("status") == "healthy" 
            for component in health_status.values() 
            if isinstance(component, dict) and "status" in component
        )
        
        health_status["overall_status"] = "healthy" if all_healthy else "unhealthy"
        
        self.health_status = health_status
        
        # Log health status
        if all_healthy:
            bot_logger.info("Health check passed", **health_status)
        else:
            bot_logger.warning("Health check failed", **health_status)
        
        return health_status
    
    def get_health_summary(self) -> str:
        """Get human-readable health summary"""
        if not self.health_status:
            return "Health check not run yet"
        
        summary = []
        summary.append(f"Overall Status: {self.health_status.get('overall_status', 'unknown')}")
        
        for component, status in self.health_status.items():
            if component in ['timestamp', 'overall_status']:
                continue
                
            if isinstance(status, dict):
                component_status = status.get('status', 'unknown')
                summary.append(f"{component.title()}: {component_status}")
                
                if component_status == 'unhealthy' and 'error' in status:
                    summary.append(f"  Error: {status['error']}")
        
        return "\n".join(summary)

# Global health checker instance
health_checker = HealthChecker()

async def get_system_health() -> Dict[str, Any]:
    """Get current system health status"""
    return await health_checker.run_full_health_check()

def get_health_summary() -> str:
    """Get human-readable health summary"""
    return health_checker.get_health_summary()

async def is_system_healthy() -> bool:
    """Check if system is overall healthy"""
    health = await get_system_health()
    return health.get("overall_status") == "healthy" 