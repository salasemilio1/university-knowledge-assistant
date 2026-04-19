"""
Requires dependency: pip install pymupdf
"""

import fitz  # PyMuPDF
import os 


def crop(input_path: str, output_path: str, page: int, rect: tuple) -> None:
    """
    Crop a single page to the given rectangle.

    Parameters
    ----------
    input_path  : path to the source PDF
    output_path : path for the cropped output PDF
    page        : 0-based page index (0 = first page)
    rect        : (x0, y0, x1, y1) crop rectangle in PDF points
    """
    doc = fitz.open(input_path)
    doc[page].set_cropbox(fitz.Rect(*rect))
    out = fitz.open()
    out.insert_pdf(doc, from_page=page, to_page=page)
    out.save(output_path, deflate=True, garbage=4, clean=True)
    out.close()
    doc.close()
    print(f"Cropped page {page} -> {output_path}")


def redact(input_path: str, output_path: str, regions: list) -> None:
    """
    Permanently redact rectangular regions from a PDF.

    Content inside each rectangle is physically destroyed in the file --
    it cannot be recovered by removing an overlay or parsing the PDF stream.

    Parameters
    ----------
    input_path  : path to the source PDF
    output_path : path for the redacted output PDF
    regions     : list of dicts, each with:
                    "page" (int)   -- 0-based page index
                    "rect" (tuple) -- (x0, y0, x1, y1) in PDF points
    Example
    -------
    regions = [
        {"page": 0, "rect": (100, 140, 400, 170)},
        {"page": 1, "rect": (60,  200, 300, 230)},
    ]
    """
    doc = fitz.open(input_path)
    for region in regions:
        page = doc[region["page"]]
        page.add_redact_annot(fitz.Rect(*region["rect"]), fill=(1, 1, 1), cross_out=False)
    for page in doc:
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True)
    doc.save(output_path, deflate=True, garbage=4, clean=True)
    doc.close()
    print(f"Redacted {len(regions)} region(s) -> {output_path}")



if __name__ == "__main__":

    # --- Redact ---------------------------------------------------------------
    redact (
        input_path  = "straight_from.pdf",
        output_path = "redacted.pdf",
        regions     = [
            {"page": 0, "rect": (10, 10, 600, 100)}
        ],
    )

    # --- Crop -----------------------------------------------------------------
    crop(
        input_path  = "redacted.pdf",
        output_path = "cropped.pdf",
        page        = 0,                    # 0 = first page
        rect        = (0, 100, 612, 792),   # (x0, y0, x1, y1)
    )