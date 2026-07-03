"""
Entry point: jalankan API + detection engine.

    python run_server.py

Akses dashboard:
    http://localhost:8000           (di PC server)
    http://<ip-LAN>:8000            (dari HP/laptop di Wi-Fi sama)
"""

from __future__ import annotations

import uvicorn

from app.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
