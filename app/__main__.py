import os
import uvicorn

def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    main()