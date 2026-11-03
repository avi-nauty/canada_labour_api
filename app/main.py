from fastapi import FastAPI

from app.routers.labour import router

app = FastAPI(
    title="Canada Labour API",
    description="A small API in front of Statistics Canada's labour force data (work in progress).",
    version="0.1.0",
)
app.include_router(router)