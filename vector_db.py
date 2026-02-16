import chromadb
import re

def md_to_string(file_path: str) -> str:
    """
    Reads the content of a Markdown file into a string.

    Args:
        file_path (str): The path of the Markdown file.

    Returns:
        str: The content of the file as a string.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            markdown_str = f.read()
        return markdown_str
    except FileNotFoundError:
        return f"The file '{file_path}' was not found."
    
def parse_metadata(md_text: str):
    """
    Get document metatdata and remaining text so it can be parsed

    Args:
        file_path (str): The text of a Markdown document.

    Returns:
        str, str: The metadata as a string
        and the remaining text in the document
    """
    _, metadata, remaining_text = md_text.split('---', 2)
    return metadata, remaining_text.strip()
    
def isolate_course_info(md_text: str) -> str:
    """
    Remove page headers, page metatdata, and menu
    navigation text from some document text
    """
    
    # Remove all page headers; ex: ## Page 1
    md_text = re.sub(r"^## Page \d+\s*$", "", md_text, flags=re.MULTILINE)

    # Remove all page metadata; ex: <!-- Page metadata: 228 words, 19 links -->
    md_text = re.sub(r"<!--\s*Page metadata:.*?", "", md_text, flags=re.DOTALL)

    # Remove menu navigation text; ex: Menu Search Apply
    md_text = re.sub(r"Menu Search.*?https://.*?\n", "", md_text, flags=re.DOTALL)

    return md_text


def chunk_by_courses(document_text: str) -> list[str]:
    """
    Breaks a document with courses into a list with courses
    and their descriptions for every course in the document text.

    Args:
        document_text (str): Text of a document with courses.

    Returns:
        list[str]: A list of strings including
        the course name and course information for every course.

    """

    

# Link to Chroma docs gettng started tutorial
# https://docs.trychroma.com/docs/overview/getting-started

chroma_client = chromadb.Client()

# Create a collection
# Collections store embeddings, documents, and metadata
collection = chroma_client.create_collection(name="university_documents")

cs_courses_str = md_to_string('/workspaces/university-knowledge-assistant/output/Courses • Southwestern University_extracted.md')



# Chroma stores text and handles embedding and indexing automatically
collection.add(
    ids=["cs_courses"],
    documents=[cs_courses_str]
)

# Query the collection
results = collection.query(
    query_texts=["Intro CS classes programming language"], # Chroma will embed this automatically
    n_results=2 # how many results to return
)
print(results)