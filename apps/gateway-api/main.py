"""Uvicorn entrypoint for Gateway API."""

from gateway.api.app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("gateway.api.app:app", host="127.0.0.1", port=8787, reload=False)
