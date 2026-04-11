from pypdf import PdfReader, PdfWriter
import re
import os 
from dotenv import load_dotenv

load_dotenv()
FILE_PATH = os.getenv("TRANSC_PATH")

reader = PdfReader(FILE_PATH)

writer = PdfWriter()

for page in reader.pages:
    # Set the crop box using coordinates (lower_left_x, lower_left_y, upper_right_x, upper_right_y)
    page.mediabox.lower_left = (0, 0)
    page.mediabox.upper_right = (500, 625)  # 800, 925
    writer.add_page(page)

with open("cropped_transc.pdf", "wb") as fp:
    writer.write(fp)

reader_cropped = PdfReader("cropped_transc.pdf")
# Extract text from the first page
page = reader_cropped.pages[0]
text = page.extract_text()
print(text)

# some regex for pattern-matching in the transcript
course_pattern = r"\b[A-Z]{3}\d{2}-\d{3}\b"

text2 = """
MAT52-164 Modern Calculus I
ENS78-101 SWE
"""

matches = re.findall(course_pattern, text2)

print(matches)
