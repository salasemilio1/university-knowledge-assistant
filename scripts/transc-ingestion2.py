import pdfplumber
import re

text = ""
with pdfplumber.open("scripts/str2.pdf") as pdf:
    page = pdf.pages[0]

    w = page.width
    h = page.height
    print(f"width: {w} and height: {h}")
    bounding_box = (0, 167, 612, 792)
    cropped_page = page.within_bbox(bounding_box)

    text = cropped_page.extract_text()
    print(text)

course_pattern = r"\b[A-Z]{3}\d{2}-\d{3}\b"

text2 = """
MAT52-164 Modern Calculus I
ENS78-101 SWE
"""

course_list = re.findall(course_pattern, text)

print(course_list)
print(len(course_list))


text3 = "APM8E-001 Flute 1.00 A+ 4.00"

pattern = r"\b([A-Z]{3}\d[A-Z]-\d{3})\s+(.+?)\s+(\d+\.\d{2})\s+([A-F][+-]?)\s+(\d+\.\d{2})\b"

match = re.search(pattern, text)

if match:
    course_code, name, credits, grade, points = match.groups()
    print(course_code, name, credits, grade, points)
