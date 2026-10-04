import os
import io
import json
import uuid
import shutil
import base64
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

from backend.app.config import (
    APPLIANCES_DIR,
    INDEX_DIR,
    OLLAMA_VISION_MODEL,
    OLLAMA_EMBED_MODEL
)
from backend.app.schemas import (
    Appliance,
    ApplianceListItem,
    ExplainResponse,
    FeedbackRequest,
    HealthResponse,
    KnowledgeAddResponse
)
from backend.app.ollama_client import OllamaClient
from backend.app.ingest import ingest_appliance_knowledge, load_appliance_index
from backend.app.explain import run_explain_pipeline
from backend.app.feedback import save_feedback

client = OllamaClient()


def _warm_up_models() -> None:
    """Load both models into memory once at startup so the first tap is not the slow one."""
    try:
        from backend.app import ocr
        ocr.warm_up()
    except Exception:
        pass
    try:
        client.get_embedding("warm up")
    except Exception:
        pass
    try:
        tiny = Image.new("RGB", (64, 64), color=(200, 200, 200))
        buf = io.BytesIO()
        tiny.save(buf, format="JPEG")
        client.generate_chat(
            prompt="Reply with OK.",
            images_b64=[base64.b64encode(buf.getvalue()).decode("utf-8")],
            model=OLLAMA_VISION_MODEL,
            num_predict=5,
        )
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background thread: the server starts answering immediately while models load.
    threading.Thread(target=_warm_up_models, daemon=True).start()
    yield


app = FastAPI(
    title="Explain This Thing API",
    description="Backend API for explaining home appliance buttons to non-technical users",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve appliance static files (e.g. panel images)
app.mount("/static/appliances", StaticFiles(directory=str(APPLIANCES_DIR)), name="static_appliances")


@app.get("/api/health", response_model=HealthResponse)
def get_health():
    status_info = client.check_health()
    is_ok = status_info.get("online", False)
    return HealthResponse(
        status="ok" if is_ok else "error",
        ollama=is_ok,
        vision_model=OLLAMA_VISION_MODEL,
        embed_model=OLLAMA_EMBED_MODEL
    )

@app.get("/api/appliances", response_model=List[ApplianceListItem])
def list_appliances():
    items = []
    if not APPLIANCES_DIR.exists():
        return items

    for folder in APPLIANCES_DIR.iterdir():
        if not folder.is_dir():
            continue
        config_file = folder / "appliance.json"
        if not config_file.exists():
            continue

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                appliance = Appliance(**data)

            # Check index chunks
            index_chunks = load_appliance_index(appliance.id)
            chunk_count = len(index_chunks)
            has_knowledge = chunk_count > 0

            items.append(ApplianceListItem(
                **appliance.model_dump(),
                has_knowledge=has_knowledge,
                chunk_count=chunk_count
            ))
        except Exception:
            continue

    return items

@app.post("/api/appliances", response_model=ApplianceListItem)
async def create_appliance(
    name: str = Form(...),
    brand: str = Form(...),
    model: str = Form(...),
    type: str = Form(...),
    language_default: str = Form("en"),
    image: Optional[UploadFile] = File(None)
):
    # Generate clean ID
    clean_id = f"{brand.lower()}_{model.lower()}".replace(" ", "_")
    clean_id = "".join([c for c in clean_id if c.isalnum() or c == "_"])
    if not clean_id:
        clean_id = f"appliance_{uuid.uuid4().hex[:6]}"

    appliance_dir = APPLIANCES_DIR / clean_id
    knowledge_dir = appliance_dir / "knowledge"
    appliance_dir.mkdir(parents=True, exist_ok=True)
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    panel_filename = "panel.jpg"
    if image:
        image_path = appliance_dir / panel_filename
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    app_data = Appliance(
        id=clean_id,
        name=name,
        brand=brand,
        model=model,
        type=type,
        panel_image=panel_filename,
        language_default=language_default
    )

    with open(appliance_dir / "appliance.json", "w", encoding="utf-8") as f:
        json.dump(app_data.model_dump(), f, indent=2)

    return ApplianceListItem(
        **app_data.model_dump(),
        has_knowledge=False,
        chunk_count=0
    )

@app.post("/api/appliances/{appliance_id}/knowledge", response_model=KnowledgeAddResponse)
async def add_knowledge(
    appliance_id: str,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    appliance_dir = APPLIANCES_DIR / appliance_id
    if not appliance_dir.exists():
        raise HTTPException(status_code=404, detail=f"Appliance '{appliance_id}' not found")

    knowledge_dir = appliance_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    if file:
        file_path = knowledge_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    elif text and text.strip():
        file_path = knowledge_dir / "notes.md"
        # Append or overwrite
        with open(file_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + text.strip())
    else:
        raise HTTPException(status_code=400, detail="Must provide either a file upload or text content")

    # Re-ingest knowledge
    chunk_count = ingest_appliance_knowledge(appliance_id, client=client)

    return KnowledgeAddResponse(
        appliance_id=appliance_id,
        chunk_count=chunk_count,
        message=f"Knowledge ingested successfully. Total chunks: {chunk_count}"
    )

@app.post("/api/explain", response_model=ExplainResponse)
async def explain_button(
    appliance_id: Optional[str] = Form(None),
    appliance_type: Optional[str] = Form(None),
    x: float = Form(...),
    y: float = Form(...),
    question: Optional[str] = Form(None),
    language: str = Form("en"),
    use_kb: bool = Form(True),
    image: Optional[UploadFile] = File(None)
):
    # Verify Ollama status
    health = client.check_health()
    if not health.get("online"):
        raise HTTPException(
            status_code=503,
            detail="Ollama server is not running. Please start Ollama server."
        )

    image_bytes = None
    if image:
        image_bytes = await image.read()
    if not image_bytes and not appliance_id:
        raise HTTPException(status_code=400, detail="Please upload a photo first.")
    if appliance_id and not (APPLIANCES_DIR / appliance_id).is_dir():
        raise HTTPException(status_code=404, detail=f"Appliance '{appliance_id}' not found")

    try:
        # Run the slow, blocking pipeline in a worker thread so /api/health etc. stay responsive.
        response = await run_in_threadpool(
            run_explain_pipeline,
            appliance_id=appliance_id,
            image_bytes=image_bytes,
            x=x,
            y=y,
            question=question,
            language=language,
            use_kb=use_kb,
            client=client,
            appliance_type_hint=appliance_type,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/feedback")
def submit_feedback(data: FeedbackRequest):
    success = save_feedback(data.request_id, data.helpful, data.comment)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to record feedback")
    return {"status": "ok", "message": "Feedback recorded successfully"}
