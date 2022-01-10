from dotenv import load_dotenv

load_dotenv()

import os
from fastapi import FastAPI
from database.db import engine
from database import models
from routers import apartments
from routers import listings
from routers import user
from routers import auth
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

models.Base.metadata.create_all(bind=engine)


origins = os.getenv("CORS_ORIGIN_SERVER")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = "/api/v1"

app.include_router(apartments.router, prefix=prefix)
app.include_router(listings.router, prefix=prefix)
app.include_router(user.router, prefix=prefix)
app.include_router(auth.router, prefix=prefix)
