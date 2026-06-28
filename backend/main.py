from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import asyncio
from dotenv import load_dotenv

from services.bootstrap import bootstrap
from services.meridian_engine import (
    process_prompt,
    get_personas_grouped,
    get_all_personas_flat,
    get_help_text,
    get_status,
    set_api_key,
    clear_session,
    get_slash_commands,
    COMMANDS_STRUCTURE,
    init_manager,
)
from services.market_dashboard import get_indices_dashboard, get_yahoo_headlines, get_market_tape

load_dotenv()
bootstrap()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_manager)
    yield


app = FastAPI(title="Meridian Finance API", version="3.0.0", lifespan=lifespan)

origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    persona_id: Optional[str] = None
    session_id: Optional[str] = "default"
    api_key: Optional[str] = None


class ApiKeyRequest(BaseModel):
    api_key: str


@app.get("/api/health")
async def health():
    status = get_status()
    return {"status": "ok", "service": "meridian-finance", **status}


@app.get("/api/personas")
async def get_personas():
    return get_all_personas_flat()


@app.get("/api/personas/grouped")
async def get_personas_grouped_endpoint():
    return get_personas_grouped()


@app.get("/api/commands")
async def get_commands():
    return COMMANDS_STRUCTURE


@app.get("/api/commands/slash")
async def get_slash_commands_endpoint():
    return get_slash_commands()


@app.get("/api/help")
async def help_text():
    return {"content": await asyncio.to_thread(get_help_text)}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        persona = req.persona_id if req.persona_id and req.persona_id.strip() else None
        result = await asyncio.to_thread(
            process_prompt,
            req.message,
            req.session_id or "default",
            persona,
            req.api_key,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/key")
async def save_key(req: ApiKeyRequest):
    """Deprecated — API keys are stored in the browser only."""
    raise HTTPException(
        status_code=410,
        detail="API keys are stored in your browser. Open Settings in the terminal.",
    )


@app.post("/api/clear/{session_id}")
async def clear(session_id: str):
    clear_session(session_id)
    return {"status": "ok"}


@app.get("/api/market/indices")
async def market_indices():
    return await asyncio.to_thread(get_indices_dashboard)


@app.get("/api/market/headlines")
async def market_headlines(limit: int = 25):
    limit = max(5, min(limit, 40))
    return await asyncio.to_thread(get_yahoo_headlines, limit)


@app.get("/api/market/tape")
async def market_tape():
    return await asyncio.to_thread(get_market_tape)
