# file to test the reconcile_chunk function
# Implement unit tests with pytest
import sys
import os

# Add the parent directory to sys.path to allow importing ingest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingest.clean_chunks import clean_text, reconcile_chunk

def test_clean_text_basic():
    """Test that clean_text removes markdown features and lowercases the text."""
    markdown_text = "## 54-144 Explorations in Computing"
    cleaned = clean_text(markdown_text)
    assert cleaned == "54-144 explorations in computing"

def test_clean_text_formatting():
    """Test that clean_text removes bold, italic, and backticks formatting."""
    formatting_text = "**Bold**, _italic_, and `code`"
    cleaned = clean_text(formatting_text)
    assert cleaned == "bold, italic, and code"

def test_reconcile_chunk_match():
    """Test that if the chunk matches the ground truth, the original markdown is preserved."""
    chunk = "## Title: **Matching** Text"
    page_text = "Some random text before. Title: Matching Text. Some random text after."
    result = reconcile_chunk(chunk, page_text)
    assert result == chunk  # Original markdown is preserved

def test_reconcile_chunk_discrepancy():
    """Test that if there is a discrepancy (ratio < 0.95), the ground-truth window is returned."""
    chunk = "## 54-144 Introduction to Computing"
    page_text = "54-144 Explorations in Computing"
    result = reconcile_chunk(chunk, page_text)
    # The returned result will be the ground-truth window
    assert result == "54-144 explorations in computing"


    # Much smaller, but realistic and important example
    chunk = "## 54-204 Algorithms and Data Structures"
    page_text = "54-284 Algorithms and Data Structures"
    result = reconcile_chunk(chunk, page_text)
    assert result == page_text.lower()