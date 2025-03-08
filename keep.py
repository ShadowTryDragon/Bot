from fastapi import FastAPI
import uvicorn
from threading import Thread

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "✅ Bot läuft 24/7!"}

def run():
    uvicorn.run(app, host="0.0.0.0", port=8080)

def keep_alive():
    server = Thread(target=run)
    server.start()
