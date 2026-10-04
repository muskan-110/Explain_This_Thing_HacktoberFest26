import pytest
from backend.app.ingest import chunk_markdown_text

def test_markdown_chunking_with_headings():
    content = """# Title
Preamble text here.

## Section One
First section body text.

## Section Two
Second section body text.
"""
    chunks = chunk_markdown_text(content, "test.md")
    assert len(chunks) == 3
    assert chunks[0]["heading"] == "Overview"
    assert chunks[1]["heading"] == "Section One"
    assert "First section body" in chunks[1]["content"]
    assert chunks[2]["heading"] == "Section Two"

def test_markdown_chunking_no_headings():
    content = "Just plain text without any h2 headers."
    chunks = chunk_markdown_text(content, "plain.txt")
    assert len(chunks) == 1
    assert chunks[0]["heading"] == "Overview"
    assert chunks[0]["content"] == "Just plain text without any h2 headers."
