# Agent Transcript 02: Multi-Container Docker Networking & Ollama Host Gateway

## Problem Statement
When running under docker compose up -d, the FastAPI backend container could not reach the local Ollama instance running on the Windows host (localhost:11434), resulting in connection timeouts and 503 errors during health checks.

## Investigation & Root Cause
Inside Docker Linux containers on Windows, localhost resolves to the container's isolated loopback interface rather than the host operating system. Furthermore, PostgreSQL was recreating its container network during restarts, leaving the backend container pointing to stale DNS aliases.

## Action Taken
1. Added extra_hosts: ["host.docker.internal:host-gateway"] to docker-compose.yml under the backend service definition.
2. Injected OLLAMA_BASE_URL: http://host.docker.internal:11434 for the backend container environment.
3. Updated Nginx reverse proxy configuration (nginx.conf) with X-Accel-Buffering: "no" and proxy_read_timeout 300s to support long-lived Server-Sent Event (SSE) streaming connections.

## Result
* Backend container communicates with host Ollama server seamlessly (HTTP 200 OK on /api/tags).
* Database healthcheck verified healthy on port 5432.