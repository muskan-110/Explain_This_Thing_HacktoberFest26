from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field

class Appliance(BaseModel):
    id: str
    name: str
    brand: str
    model: str
    type: str
    panel_image: str = "panel.jpg"
    language_default: str = "en"

class ApplianceListItem(Appliance):
    has_knowledge: bool = False
    chunk_count: int = 0

class ReadResult(BaseModel):
    label_text: str = Field(description="Printed text or numbers on or near the button, or empty string if none")
    icon_description: str = Field(description="Visual shape or icon on the button, e.g. power symbol, fan blades, clock")
    looks_like: str = Field(description="Brief physical appearance description of the button")

class ExplainResult(BaseModel):
    button_name: str = Field(description="Name of the button exactly as printed or recognized")
    what_it_does: str = Field(description="Simple 1-sentence explanation of what the button does")
    try_this: str = Field(description="Simple 1-sentence instruction on what to press or try")
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence level in the answer")
    source: Literal["knowledge_base", "general_knowledge"] = Field(description="Source of the explanation")
    source_ref: Optional[str] = Field(default=None, description="Filename and section/page reference if from knowledge base")
    passages_cover_button: bool = Field(default=True, description="True if provided manual passages explicitly cover this button")
    safety_flag: bool = Field(default=False, description="True if unsafe condition detected")
    hindi_failed: bool = Field(default=False, description="True if Hindi translation failed after retries")

class Timings(BaseModel):
    crop_ms: float = 0.0
    read_ms: float = 0.0
    embed_ms: float = 0.0
    retrieve_ms: float = 0.0
    explain_ms: float = 0.0
    total_ms: float = 0.0

class RetrievedChunkInfo(BaseModel):
    chunk_id: str
    filename: str
    heading: str
    content: str
    score: float

class ExplainResponse(BaseModel):
    request_id: str
    card: ExplainResult
    read_result: ReadResult
    retrieved_chunks: List[RetrievedChunkInfo] = []
    timings: Timings
    mode: Literal["kb", "no_kb"]
    cropped_image_base64: Optional[str] = None
    marked_image_base64: Optional[str] = None

class FeedbackRequest(BaseModel):
    request_id: str
    helpful: bool
    comment: Optional[str] = None

class KnowledgeAddResponse(BaseModel):
    appliance_id: str
    chunk_count: int
    message: str

class HealthResponse(BaseModel):
    status: str
    ollama: bool
    vision_model: str
    embed_model: str
