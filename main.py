"""
Application server entry point.
"""

import uvicorn
from src.utils.config import settings


def main():
    print(f"Starting PlacidWay Assistant on {settings.HOST}:{settings.PORT}...")
    uvicorn.run(
        "src.api.app:app",
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
