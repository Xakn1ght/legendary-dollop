# Health Check Endpoint Documentation

## Overview

The health check endpoint provides comprehensive system status monitoring for the ASSTRO bot application. It checks the health of all critical and optional services.

## Endpoints

- `GET /health`
- `GET /api/health`

Both endpoints return the same response.

## Response Format

```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "2025-12-12T10:30:00.000000Z",
  "checks": {
    "database": {
      "status": "ok",
      "latency_ms": 5.23
    },
    "marzban": {
      "status": "ok",
      "latency_ms": 120.45
    },
    "redis": {
      "status": "ok",
      "latency_ms": 2.11
    },
    "bot": {
      "status": "running",
      "bot_username": "YourBotUsername",
      "bot_id": 123456789
    },
    "scheduler": {
      "status": "running",
      "pending_jobs": 5,
      "jobs": [
        {
          "id": "check_low_data_job",
          "name": "check_low_data_job",
          "next_run": "2025-12-12T11:00:00"
        }
      ]
    }
  },
  "version": "1.0.0",
  "response_time_ms": 125.67
}
```

## Status Codes

### HTTP Status Codes

- `200 OK` - System is healthy or degraded (still operational)
- `503 Service Unavailable` - System is unhealthy (critical services down)

### Service Status Values

Each service check can return one of the following statuses:

- `ok` - Service is fully operational
- `running` - Service is active (for bot and scheduler)
- `degraded` - Service is operational but experiencing issues
- `unavailable` - Service is not available (non-critical)
- `error` - Service check failed
- `timeout` - Service check timed out
- `stopped` - Service is not running (for scheduler)

## Health Determination Logic

### Overall Status

The overall system status is determined by:

1. **Healthy** - All critical services are `ok` and optional services are operational
2. **Degraded** - All critical services are operational but some services have issues
3. **Unhealthy** - One or more critical services are down

### Critical Services

Services that must be operational for the system to function:
- Database
- Marzban API
- Bot

### Optional Services

Services that enhance functionality but aren't critical:
- Redis (system falls back to in-memory cache)
- Scheduler

## Use Cases

### 1. Load Balancer Health Checks

Configure your load balancer to perform health checks:

```nginx
# Nginx upstream health check
upstream asstro_backend {
    server localhost:8080;
    
    # Health check configuration
    health_check interval=10s fails=3 passes=2 uri=/health;
}
```

### 2. Uptime Monitoring

Use tools like UptimeRobot, Pingdom, or custom monitoring:

- **URL**: `https://your-domain.com/health`
- **Check Interval**: Every 30-60 seconds
- **Alert Conditions**: 
  - HTTP status 503
  - Response status field is "unhealthy"

### 3. Kubernetes Liveness/Readiness Probes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: asstro-bot
spec:
  containers:
  - name: asstro
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 30
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 2
```

### 4. Docker Compose Healthcheck

```yaml
version: '3.8'
services:
  asstro-bot:
    image: asstro-bot:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 5. Monitoring Dashboards

Parse the JSON response to display service status:

```javascript
// Example: Fetch and display health status
async function checkHealth() {
  const response = await fetch('/health');
  const health = await response.json();
  
  console.log('System Status:', health.status);
  console.log('Database Latency:', health.checks.database.latency_ms, 'ms');
  console.log('Marzban API Latency:', health.checks.marzban.latency_ms, 'ms');
  
  // Display in dashboard
  updateStatusIndicator(health.status);
  updateServiceMetrics(health.checks);
}
```

## Service Check Details

### Database Check

- Executes `SELECT 1` query to verify connectivity
- Measures query latency
- Returns error details if connection fails

### Marzban API Check

- Attempts to connect to Marzban `/api/system` endpoint
- Tests authentication and API availability
- Automatic re-authentication on 401 errors
- 5-second timeout to prevent hanging
- Measures total latency including retry if needed

### Redis Check

- Sends `PING` command to Redis
- Returns "unavailable" if Redis client not initialized
- System continues to function with in-memory fallback

### Bot Check

- Verifies bot instance is available
- Calls `get_me()` to confirm bot is active
- Returns bot username and ID

### Scheduler Check

- Verifies scheduler is running
- Returns count of pending jobs
- Lists up to 5 jobs with next run times
- Useful for monitoring background task execution

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Overall system health: "healthy", "degraded", or "unhealthy" |
| `timestamp` | string | ISO 8601 timestamp of the health check |
| `checks` | object | Individual service health checks |
| `version` | string | API version (currently "1.0.0") |
| `response_time_ms` | number | Total time taken to perform all health checks |

## Error Handling

The health check endpoint is designed to be resilient:

- Individual service failures don't crash the endpoint
- Exceptions are caught and returned as error statuses
- Concurrent checks with `asyncio.gather(return_exceptions=True)`
- Timeouts prevent hanging on unresponsive services

## Performance Considerations

- All checks run concurrently for fast response times
- Typical response time: 50-200ms (depending on service latencies)
- Marzban check has 5-second timeout
- Database check is a lightweight SELECT 1 query
- Redis PING is extremely fast (<5ms typically)

## Security Notes

- The endpoint does not require authentication (by design for health checks)
- No sensitive information is exposed
- Error messages are generic (don't expose internal details)
- Bot username/ID are public information anyway

## Troubleshooting

### Health Check Returns 503

This means one or more critical services are down. Check the `checks` object to see which service is failing.

### Marzban Shows "degraded"

This could be due to:
- Slow API response (high latency)
- Temporary authentication issues
- Network connectivity problems

### Redis Shows "unavailable"

This is usually not critical. The system continues to work with in-memory caching. Check:
- Redis server is running
- Connection settings in `.env` file
- Network connectivity to Redis

### Scheduler Shows "stopped"

The background job scheduler isn't running. This means:
- No automatic notifications
- No periodic updates
- No scheduled maintenance tasks

Check the bot logs for scheduler startup errors.

## Examples

### Healthy System

```bash
$ curl http://localhost:8080/health
```

```json
{
  "status": "healthy",
  "timestamp": "2025-12-12T10:30:00.000000Z",
  "checks": {
    "database": {"status": "ok", "latency_ms": 5.23},
    "marzban": {"status": "ok", "latency_ms": 120.45},
    "redis": {"status": "ok", "latency_ms": 2.11},
    "bot": {"status": "running", "bot_username": "asstro_bot", "bot_id": 123456789},
    "scheduler": {"status": "running", "pending_jobs": 5}
  },
  "version": "1.0.0",
  "response_time_ms": 125.67
}
```

### Degraded System (Redis Down)

```json
{
  "status": "degraded",
  "timestamp": "2025-12-12T10:35:00.000000Z",
  "checks": {
    "database": {"status": "ok", "latency_ms": 6.12},
    "marzban": {"status": "ok", "latency_ms": 115.23},
    "redis": {"status": "unavailable", "error": "Connection refused"},
    "bot": {"status": "running", "bot_username": "asstro_bot", "bot_id": 123456789},
    "scheduler": {"status": "running", "pending_jobs": 5}
  },
  "version": "1.0.0",
  "response_time_ms": 120.45
}
```

### Unhealthy System (Database Down)

HTTP Status: 503 Service Unavailable

```json
{
  "status": "unhealthy",
  "timestamp": "2025-12-12T10:40:00.000000Z",
  "checks": {
    "database": {"status": "error", "error": "Connection refused", "latency_ms": 5000},
    "marzban": {"status": "ok", "latency_ms": 110.34},
    "redis": {"status": "ok", "latency_ms": 2.45},
    "bot": {"status": "running", "bot_username": "asstro_bot", "bot_id": 123456789},
    "scheduler": {"status": "running", "pending_jobs": 5}
  },
  "version": "1.0.0",
  "response_time_ms": 5200.67
}
```

## Integration with Monitoring Systems

### Prometheus

Create a custom exporter that scrapes the health endpoint:

```python
# Example: Convert health check to Prometheus metrics
from prometheus_client import Gauge

service_status = Gauge('service_health_status', 'Service health status', ['service'])
service_latency = Gauge('service_latency_ms', 'Service latency in ms', ['service'])

async def update_metrics():
    health = await fetch_health()
    for service, data in health['checks'].items():
        status_value = 1 if data['status'] in ['ok', 'running'] else 0
        service_status.labels(service=service).set(status_value)
        if 'latency_ms' in data:
            service_latency.labels(service=service).set(data['latency_ms'])
```

### Grafana Dashboard

Create panels to visualize:
- Overall system status (single stat)
- Service latencies (time series graph)
- Service availability (status panel)
- Historical uptime (stat panel)

### Custom Alerting

```python
import requests

def check_and_alert():
    response = requests.get('http://localhost:8080/health')
    health = response.json()
    
    if health['status'] == 'unhealthy':
        send_alert(f"CRITICAL: System unhealthy - {health}")
    elif health['status'] == 'degraded':
        send_warning(f"WARNING: System degraded - {health}")
    
    # Check individual service latencies
    if health['checks']['database']['latency_ms'] > 1000:
        send_warning("Database latency high")
    if health['checks']['marzban']['latency_ms'] > 5000:
        send_warning("Marzban API latency high")
```

## Changelog

### Version 1.0.0 (2025-12-12)

- Initial release
- Database connectivity check
- Marzban API connectivity check
- Redis availability check
- Bot status check
- Scheduler status check
- Concurrent health checks for performance
- Comprehensive error handling
