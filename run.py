"""
Production runner for Render / Cloud deployment.
Safely extracts PORT and HOST from environment variables with fallback handling.
"""

import os
import uvicorn

if __name__ == "__main__":
    raw_port = os.environ.get("PORT", "10000")
    try:
        port = int(raw_port)
    except (ValueError, TypeError):
        # In case PORT was accidentally assigned an IP like "0.0.0.0"
        port = 10000

    host = "0.0.0.0"
    print(f"Starting server on {host}:{port}...")
    uvicorn.run("app.main:app", host=host, port=port)
