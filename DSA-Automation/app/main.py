from fastapi import FastAPI

from app import database
from app.database import Base, engine
from app.models.problem import Problem
from app.routers import problems
from app.routers import github_webhook
from app.models.draft import Draft
from app.routers.review import router as review_router

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(problems.router)
app.include_router(github_webhook.router)
app.include_router(review_router)