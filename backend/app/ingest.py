import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any
import pymupdf as fitz

from backend.app.config import APPLIANCES_DIR, INDEX_DIR
from backend.app.ollama_client import OllamaClient

def chunk_markdown_text(content: str, filename: str) -> List[Dict[str, str]]:
    """
    Splits markdown or plain text content on '## ' headings.
    Returns list of dicts with 'heading', 'content', 'filename'.
    """
    chunks = []
    # Normalize line endings
    content = content.replace("\r\n", "\n")
    
    # Check if there are '## ' headings
    if "## " not in content:
        cleaned = content.strip()
        if cleaned:
            chunks.append({
                "filename": filename,
                "heading": "Overview",
                "content": cleaned
            })
        return chunks

    # Split by '## '
    sections = re.split(r'\n(?=## )', content)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        
        lines = section.split("\n")
        first_line = lines[0].strip()
        
        if first_line.startswith("## "):
            heading = first_line[3:].strip()
            body = "\n".join(lines[1:]).strip()
            chunk_content = f"{heading}\n{body}" if body else heading
        else:
            # Preamble before first ## heading
            heading = "Overview"
            chunk_content = section

        if chunk_content:
            chunks.append({
                "filename": filename,
                "heading": heading,
                "content": chunk_content
            })
            
    return chunks

def chunk_pdf(file_path: Path, filename: str, words_per_chunk: int = 300, overlap_words: int = 50) -> List[Dict[str, str]]:
    """
    Extracts text from PDF page by page using PyMuPDF and splits into ~300-word chunks with overlap.
    """
    chunks = []
    doc = fitz.open(file_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if not text:
            continue

        words = text.split()
        if len(words) <= words_per_chunk:
            chunks.append({
                "filename": filename,
                "heading": f"Page {page_num + 1}",
                "content": text
            })
        else:
            start = 0
            chunk_idx = 1
            while start < len(words):
                end = min(start + words_per_chunk, len(words))
                chunk_words = words[start:end]
                chunk_text = " ".join(chunk_words)
                chunks.append({
                    "filename": filename,
                    "heading": f"Page {page_num + 1} (Part {chunk_idx})",
                    "content": chunk_text
                })
                chunk_idx += 1
                start += words_per_chunk - overlap_words

    doc.close()
    return chunks

def ingest_appliance_knowledge(appliance_id: str, client: OllamaClient = None) -> int:
    """
    Ingests all .md, .txt, and .pdf files in data/appliances/<appliance_id>/knowledge/
    Generates embeddings and saves cache to data/index/<appliance_id>.json.
    Returns total chunk count.
    """
    if client is None:
        client = OllamaClient()

    appliance_dir = APPLIANCES_DIR / appliance_id
    knowledge_dir = appliance_dir / "knowledge"
    
    raw_chunks: List[Dict[str, str]] = []

    if knowledge_dir.exists() and knowledge_dir.is_dir():
        for file_path in knowledge_dir.iterdir():
            if not file_path.is_file():
                continue
            
            ext = file_path.suffix.lower()
            filename = file_path.name

            if ext in [".md", ".txt"]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                raw_chunks.extend(chunk_markdown_text(content, filename))

            elif ext == ".pdf":
                raw_chunks.extend(chunk_pdf(file_path, filename))

    if not raw_chunks:
        # Save empty index
        index_path = INDEX_DIR / f"{appliance_id}.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump([], f)
        return 0

    indexed_chunks = []
    for idx, c in enumerate(raw_chunks):
        chunk_id = f"{appliance_id}::{c['filename']}::{c['heading']}::{idx}"
        # Get embedding from Ollama
        embedding = client.get_embedding(c["content"])
        
        indexed_chunks.append({
            "chunk_id": chunk_id,
            "appliance_id": appliance_id,
            "filename": c["filename"],
            "heading": c["heading"],
            "content": c["content"],
            "embedding": embedding
        })

    index_path = INDEX_DIR / f"{appliance_id}.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(indexed_chunks, f, indent=2)

    return len(indexed_chunks)

def load_appliance_index(appliance_id: str) -> List[Dict[str, Any]]:
    """Loads indexed chunks for an appliance from data/index/<appliance_id>.json."""
    index_path = INDEX_DIR / f"{appliance_id}.json"
    if not index_path.exists():
        return []
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
