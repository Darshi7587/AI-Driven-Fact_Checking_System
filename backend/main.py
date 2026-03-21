from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from config import CORS_ORIGINS, MONGODB_URL, DATABASE_NAME
from routes.auth_routes import router as auth_router
from routes.verification_routes import router as verification_router
from routes.history_routes import router as history_router

db_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client
    db_client = AsyncIOMotorClient(MONGODB_URL)
    app.state.db = db_client[DATABASE_NAME]
    print(f"✅ Connected to MongoDB: {DATABASE_NAME}")
    yield
    db_client.close()
    print("🔌 Disconnected from MongoDB")

app = FastAPI(
    title="VeritAI API",
    description="AI-powered Fact & Claim Verification Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(verification_router, prefix="/api/verify", tags=["Verification"])
app.include_router(history_router, prefix="/api/history", tags=["History"])

@app.get("/")
async def root():
    return {"message": "VeritAI API is running 🚀", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "VeritAI"}
