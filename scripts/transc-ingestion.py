import pdfplumber
import re
import os 
from dotenv import load_dotenv

load_dotenv()
FILE_PATH = os.getenv("TRANSC_PATH")

text = ""
with pdfplumber.open(FILE_PATH) as pdf:
    page = pdf.pages[0]

    w = page.width
    h = page.height
    print(f"width: {w} and height: {h}")
    bounding_box = (0, 167, 612, 792)
    cropped_page = page.within_bbox(bounding_box)

    text = cropped_page.extract_text()
    print(text, "test")

#course_pattern = r"\b([A-Z]{2,4}\d{2}-\d{3})\b[A-Z]{3}\d{2}-\d{3}\s+(.+?)\s+\d+\.\d{2}\s+[A-F][+-]?\s+\d+\.\d{2}\b"

course_code_pattern = r"\b[A-Z]{2,4}(?:\d{2}|\d[A-Z])-\d{3}\b"
course_name_pattern = r"\b[A-Z]{3}\d{2}-\d{3}\s+(.+?)\s+\d+\.\d{2}\s+[A-F][+-]?\s+\d+\.\d{2}\b"
course_credits_and_grade_pattern = r"\b(\d+\.\d{2})\s+([A-F][+-]?)\b" # can be broken up in groups


# course_list = re.findall(course_pattern, text)
course_code_list = re.findall(course_code_pattern, text)
course_name_list = re.findall(course_name_pattern, text)
match = re.search(course_credits_and_grade_pattern, text)
course_credits, course_grade = match.groups()

print(f"Course Codes: {course_code_list}")
print(f"\nNumber of Course Codes: {len(course_code_list)}")

print(f"\nCourse Names: {course_name_list}")
print(f"\nNumber of Course Names: {len(course_name_list)}")
# print(f"\nFull Course Information: {course_list}")

print(f"\nCourse Credits + Grade Pattern: {course_credits_and_grade_pattern}")
print(f"\nCourse Credits and Grade: {course_credits} and {course_grade}")


#pattern = r"\b([A-Z]{3}\d[A-Z]-\d{3})\s+(.+?)\s+(\d+\.\d{2})\s+([A-F][+-]?)\s+(\d+\.\d{2})\b"
pattern = r"\b([A-Z]{2,4}\d{2}-\d{3})\s+(.+?)\s+(\d+\.\d{2})\s+([A-F][+-]?)\s+(\d+\.\d{2})\b"

match = re.search(pattern, text)
print(f"Matches: {match}")
if match:
    course_code, name, credits, grade, points = match.groups()
    print(course_code, name, credits, grade, points)
    print("testing")


