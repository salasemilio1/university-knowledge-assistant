#!/usr/bin/env python3
from pathlib import Path
import sys

def main():
    # Setup path to knowledge_base, assuming script is in the scripts/ folder
    kb_root = Path(__file__).resolve().parent.parent / "knowledge_base"
    
    if not kb_root.exists() or not kb_root.is_dir():
        print(f"Error: Knowledge base directory not found at {kb_root}")
        sys.exit(1)

    # Find directories lacking a skills_index.md
    missing_skills = [
        d.name for d in sorted(kb_root.iterdir())
        if d.is_dir() and not (d / "skills_index.md").exists()
    ]

    # Print results
    for major in missing_skills:
        print(major)

if __name__ == "__main__":
    main()
