"""
PDF Metadata Extractor for University RAG System
Extracts text and builds hierarchical metadata from PDFs using an immutable approach.

Metadata levels:
1. Document metadata
2. Page metadata
3. Region metadata (future)
4. Chunk metadata (future)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib

try:
    from pypdf import PdfReader
except ImportError:
    print("Installing pypdf...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf", "--break-system-packages"])
    from pypdf import PdfReader


@dataclass
class DocumentMetadata:
    """Immutable document-level metadata"""
    file_path: str
    file_name: str
    file_size_bytes: int
    file_hash: str  # SHA256 hash for deduplication
    total_pages: int
    extraction_timestamp: str
    pdf_metadata: Dict[str, Any]  # Title, Author, Subject, etc.
    document_type: Optional[str] = None  # e.g., "syllabus", "handbook", "policy"
    academic_year: Optional[str] = None
    department: Optional[str] = None
    

@dataclass
class PageMetadata:
    """Immutable page-level metadata"""
    page_number: int  # 1-indexed
    page_index: int  # 0-indexed
    width: float
    height: float
    rotation: int
    text_length: int
    word_count: int
    has_images: bool
    has_links: bool
    link_count: int
    # Inherited from document
    document_hash: str
    document_name: str


@dataclass
class PageContent:
    """Page content with metadata"""
    metadata: PageMetadata
    text: str
    raw_text: str  # Preserve original extraction
    links: List[Dict[str, Any]]
    

@dataclass
class DocumentBundle:
    """Complete document with all metadata and content"""
    document_metadata: DocumentMetadata
    pages: List[PageContent]
    

class PDFMetadataExtractor:
    """Extract text and metadata from PDFs for RAG system"""
    
    def __init__(self):
        self.supported_extensions = {'.pdf'}
    
    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file for deduplication"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def extract_document_metadata(self, pdf_path: Path, reader: PdfReader) -> DocumentMetadata:
        """Extract document-level metadata"""
        
        # Get PDF metadata
        pdf_meta = reader.metadata or {}
        
        # Clean up metadata values - pypdf uses different attribute names
        cleaned_meta = {}
        if pdf_meta:
            # pypdf uses attributes like .title, .author, .subject
            for attr in ['title', 'author', 'subject', 'creator', 'producer', 'creation_date', 'modification_date']:
                value = getattr(pdf_meta, f'/{attr.capitalize()}', None) or getattr(pdf_meta, attr, None)
                if value:
                    cleaned_meta[attr] = str(value).strip() if value else None
        
        return DocumentMetadata(
            file_path=str(pdf_path.absolute()),
            file_name=pdf_path.name,
            file_size_bytes=pdf_path.stat().st_size,
            file_hash=self.compute_file_hash(pdf_path),
            total_pages=len(reader.pages),
            extraction_timestamp=datetime.utcnow().isoformat() + "Z",
            pdf_metadata=cleaned_meta,
            document_type=self._infer_document_type(pdf_path.name, cleaned_meta),
            academic_year=self._extract_academic_year(pdf_path.name, cleaned_meta),
            department=self._extract_department(cleaned_meta)
        )
    
    def _infer_document_type(self, filename: str, metadata: Dict) -> Optional[str]:
        """Infer document type from filename and metadata"""
        filename_lower = filename.lower()
        title = metadata.get('title', '').lower() if metadata.get('title') else ''
        
        # Simple heuristics - expand based on your university's document types
        if 'syllabus' in filename_lower or 'syllabus' in title:
            return 'syllabus'
        elif 'handbook' in filename_lower or 'handbook' in title:
            return 'handbook'
        elif 'policy' in filename_lower or 'polic' in title:
            return 'policy'
        elif 'catalog' in filename_lower or 'catalog' in title:
            return 'catalog'
        elif 'schedule' in filename_lower or 'schedule' in title:
            return 'schedule'
        elif 'guideline' in filename_lower or 'guideline' in title:
            return 'guidelines'
        
        return None
    
    def _extract_academic_year(self, filename: str, metadata: Dict) -> Optional[str]:
        """Extract academic year from filename or metadata"""
        import re
        
        # Look for patterns like 2024-2025, 2024, Fall2024, etc.
        year_patterns = [
            r'20\d{2}[-_]20\d{2}',  # 2024-2025
            r'20\d{2}',  # 2024
            r'(Fall|Spring|Summer)\s*20\d{2}',  # Fall 2024
        ]
        
        search_text = f"{filename} {metadata.get('title', '')} {metadata.get('subject', '')}"
        
        for pattern in year_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_department(self, metadata: Dict) -> Optional[str]:
        """Extract department from metadata"""
        # Check common metadata fields
        author = metadata.get('author', '')
        subject = metadata.get('subject', '')
        
        # You can expand this with your university's department names
        common_departments = [
            'Computer Science', 'CS', 'Mathematics', 'Physics', 
            'Biology', 'Chemistry', 'English', 'History',
            'Registrar', 'Admissions', 'Student Affairs'
        ]
        
        search_text = f"{author} {subject}".lower()
        
        for dept in common_departments:
            if dept.lower() in search_text:
                return dept
        
        return None
    
    def extract_page_metadata(
        self, 
        page,
        page_num: int,
        doc_hash: str,
        doc_name: str
    ) -> PageMetadata:
        """Extract page-level metadata"""
        
        # Get page dimensions (pypdf uses mediabox)
        mediabox = page.mediabox
        width = float(mediabox.width)
        height = float(mediabox.height)
        rotation = int(page.get('/Rotate', 0))
        
        # Extract text for analysis
        text = page.extract_text()
        word_count = len(text.split()) if text else 0
        
        # Check for images - pypdf
        has_images = False
        try:
            if '/Resources' in page and '/XObject' in page['/Resources']:
                xobjects = page['/Resources']['/XObject'].get_object()
                has_images = any(
                    obj.get('/Subtype') == '/Image' 
                    for obj in xobjects.values()
                    if hasattr(obj, 'get')
                )
        except:
            pass
        
        # Check for links/annotations
        has_links = False
        link_count = 0
        try:
            if '/Annots' in page:
                annots = page['/Annots']
                if annots:
                    link_count = len(annots)
                    has_links = link_count > 0
        except:
            pass
        
        return PageMetadata(
            page_number=page_num + 1,  # 1-indexed for humans
            page_index=page_num,  # 0-indexed for systems
            width=width,
            height=height,
            rotation=rotation,
            text_length=len(text) if text else 0,
            word_count=word_count,
            has_images=has_images,
            has_links=has_links,
            link_count=link_count,
            document_hash=doc_hash,
            document_name=doc_name
        )
    
    def extract_page_content(
        self, 
        page,
        page_num: int,
        doc_hash: str,
        doc_name: str
    ) -> PageContent:
        """Extract full page content with metadata"""
        
        # Extract text
        raw_text = page.extract_text() or ""
        
        # Clean text (basic cleaning - expand as needed)
        text = self._clean_text(raw_text)
        
        # Extract links/annotations
        links = []
        try:
            if '/Annots' in page:
                annots = page['/Annots']
                if annots:
                    for annot in annots:
                        try:
                            annot_obj = annot.get_object()
                            link_info = {
                                'type': str(annot_obj.get('/Subtype', 'Unknown')),
                                'uri': str(annot_obj.get('/A', {}).get('/URI', '')),
                                'rect': str(annot_obj.get('/Rect', ''))
                            }
                            links.append(link_info)
                        except:
                            pass
        except:
            pass
        
        # Build page metadata
        metadata = self.extract_page_metadata(page, page_num, doc_hash, doc_name)
        
        return PageContent(
            metadata=metadata,
            text=text,
            raw_text=raw_text,
            links=links
        )
    
    def _clean_text(self, text: str) -> str:
        """Basic text cleaning"""
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text
    
    def process_pdf(self, pdf_path: Path) -> DocumentBundle:
        """Process a single PDF and extract all metadata"""
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        if pdf_path.suffix.lower() not in self.supported_extensions:
            raise ValueError(f"Unsupported file type: {pdf_path.suffix}")
        
        print(f"Processing: {pdf_path.name}")
        
        # Open PDF with pypdf
        reader = PdfReader(pdf_path)
        
        # Extract document metadata
        doc_metadata = self.extract_document_metadata(pdf_path, reader)
        print(f"  - Document: {doc_metadata.total_pages} pages")
        
        # Extract page content
        pages = []
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            page_content = self.extract_page_content(
                page, 
                page_num,
                doc_metadata.file_hash,
                doc_metadata.file_name
            )
            pages.append(page_content)
            
            if (page_num + 1) % 10 == 0:
                print(f"  - Processed {page_num + 1}/{doc_metadata.total_pages} pages")
        
        print(f"  ✓ Complete: {len(pages)} pages extracted")
        
        return DocumentBundle(
            document_metadata=doc_metadata,
            pages=pages
        )
    
    def save_as_json(self, bundle: DocumentBundle, output_path: Path):
        """Save document bundle as JSON"""
        
        # Convert to dictionary
        data = {
            'document_metadata': asdict(bundle.document_metadata),
            'pages': [
                {
                    'metadata': asdict(page.metadata),
                    'text': page.text,
                    'raw_text': page.raw_text,
                    'links': page.links
                }
                for page in bundle.pages
            ]
        }
        
        # Write JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Saved JSON: {output_path}")
    
    def save_as_markdown(self, bundle: DocumentBundle, output_path: Path):
        """Save document bundle as Markdown with frontmatter"""
        
        doc_meta = bundle.document_metadata
        
        # Build YAML frontmatter
        frontmatter = ["---"]
        frontmatter.append(f"file_name: {doc_meta.file_name}")
        frontmatter.append(f"file_hash: {doc_meta.file_hash}")
        frontmatter.append(f"total_pages: {doc_meta.total_pages}")
        frontmatter.append(f"extraction_timestamp: {doc_meta.extraction_timestamp}")
        
        if doc_meta.document_type:
            frontmatter.append(f"document_type: {doc_meta.document_type}")
        if doc_meta.academic_year:
            frontmatter.append(f"academic_year: {doc_meta.academic_year}")
        if doc_meta.department:
            frontmatter.append(f"department: {doc_meta.department}")
        
        # Add PDF metadata
        if doc_meta.pdf_metadata:
            frontmatter.append("pdf_metadata:")
            for key, value in doc_meta.pdf_metadata.items():
                frontmatter.append(f"  {key}: {value}")
        
        frontmatter.append("---\n")
        
        # Build markdown content
        lines = frontmatter
        lines.append(f"# {doc_meta.file_name}\n")
        
        for page in bundle.pages:
            lines.append(f"\n## Page {page.metadata.page_number}")
            lines.append(f"<!-- Page metadata: {page.metadata.word_count} words, "
                        f"{'has images, ' if page.metadata.has_images else ''}"
                        f"{page.metadata.link_count} links -->\n")
            lines.append(page.text)
            lines.append("\n")
        
        # Write markdown
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"✓ Saved Markdown: {output_path}")


def main():
    """Example usage"""
    
    # Initialize extractor
    extractor = PDFMetadataExtractor()
    
    # Example: Process a PDF
    # You can replace this with your actual PDF path
    pdf_path = Path("sample_university_document.pdf")
    
    # For demonstration, let's show what the code does
    print("=" * 60)
    print("PDF Metadata Extractor - University RAG System")
    print("=" * 60)
    print("\nThis script extracts text and metadata from PDFs using")
    print("a hierarchical, immutable approach:\n")
    print("  1. Document metadata (file info, PDF properties)")
    print("  2. Page metadata (dimensions, content stats)")
    print("  3. [Future] Region metadata (layout detection)")
    print("  4. [Future] Chunk metadata (for RAG)")
    print("\n" + "=" * 60)
    
    # Check if a PDF file is provided
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
        
        try:
            # Process PDF
            bundle = extractor.process_pdf(pdf_path)
            
            # Create output directory
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            # Save as JSON
            json_path = output_dir / f"{pdf_path.stem}_metadata.json"
            extractor.save_as_json(bundle, json_path)
            
            # Save as Markdown
            md_path = output_dir / f"{pdf_path.stem}_extracted.md"
            extractor.save_as_markdown(bundle, md_path)
            
            # Print summary
            print("\n" + "=" * 60)
            print("EXTRACTION SUMMARY")
            print("=" * 60)
            print(f"Document: {bundle.document_metadata.file_name}")
            print(f"Type: {bundle.document_metadata.document_type or 'Unknown'}")
            print(f"Pages: {bundle.document_metadata.total_pages}")
            print(f"Total words: {sum(p.metadata.word_count for p in bundle.pages):,}")
            print(f"File hash: {bundle.document_metadata.file_hash[:16]}...")
            
            if bundle.document_metadata.academic_year:
                print(f"Academic year: {bundle.document_metadata.academic_year}")
            
            print("\n✓ Extraction complete!")
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print("\nUSAGE:")
        print("  python pdf_metadata_extractor.py <path_to_pdf>")
        print("\nEXAMPLE:")
        print("  python pdf_metadata_extractor.py syllabus_2024.pdf")
        print("\nOUTPUT:")
        print("  - JSON file with complete metadata")
        print("  - Markdown file with extracted text")
        print("  - Both saved in ./output/ directory")
        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()