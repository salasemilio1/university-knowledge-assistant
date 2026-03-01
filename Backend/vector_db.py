import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import re
import sys

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
    md_text = re.sub(r"<!--\s*Page metadata:.*?-->", "", md_text, flags=re.DOTALL)

    # Remove menu navigation text; ex: Menu Search Apply
    md_text = re.sub(r"Menu Search.*?https://.*?\n", "", md_text, flags=re.DOTALL)

    # Remove text from links at the bottom of the page
    md_text = re.sub(r"GEORGETOWN, TEXAS.*", "", md_text)

    return md_text.strip()


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
    seen_course_codes = set()

    def add_newline_once(match: re.Match):
        """
        Ensures that newline is added for the first time a course code appears.

        Args:
            match (re.Match): Match found by regex which contains course code
            and an extra captial letter following it after a space.

        Returns:
            newline appended to course_code if it is the first instance,
            otherwise just the course code.
        """
        match_text = match.group(1)
        course_code = match_text[:6]

        if course_code in seen_course_codes:
            return match_text
        else:
            seen_course_codes.add(course_code)
            return "\n" + match_text
        
    document_text = re.sub(r"(\d{2}-\d{3} [A-Z])", add_newline_once, document_text)
    chunks = re.split(r"(?=\n\d{2}-\d{3} [A-Z])", document_text, flags=re.MULTILINE)
    return chunks

def main():
    # Link to Chroma docs gettng started tutorial
    # https://docs.trychroma.com/docs/overview/getting-started

    chroma_client = chromadb.Client()

    # Try a different embedding function than the default
    sentence_transformer_ef = SentenceTransformerEmbeddingFunction(
        model_name="all-mpnet-base-v2",
        device="cpu",
        normalize_embeddings=False
    )

    # Create a collection
    # Collections store embeddings, documents, and metadata
    collection = chroma_client.create_collection(name="university_documents", embedding_function=sentence_transformer_ef)

    cs_courses_path = '/workspaces/university-knowledge-assistant/output/SU_CS_Overview_extracted.md'
    # If there is a path provided as an argument, use it
    if len(sys.argv) > 1:
        cs_courses_path = sys.argv[1]
    cs_courses_str = md_to_string(cs_courses_path)
    

    # Separate metadata from the rest of the content
    cs_courses_metadata, cs_courses_str = parse_metadata(cs_courses_str)
    cs_courses_str = isolate_course_info(cs_courses_str)

    # Break up courses into chunks
    cs_course_chunks = chunk_by_courses(cs_courses_str)

    cs_courses_metadata = {"file_name": "SU_CS_Overview.pdf",
        "file_size_bytes": 202425,
    "file_hash": "8ca86e2913df0a31aad8b7ca71e15af7ff7789e31b5f2d8d39cfc5fb6f29e237",
        "total_pages": 5}

    # Create copy of the document metadata for every cs course chunk.
    cs_courses_metadatas = [cs_courses_metadata.copy() for _ in cs_course_chunks]

    # Create the embeddings using the new embedding function
    # embeddings = sentence_transformer_ef(cs_course_chunks)


    # Chroma stores text and handles embedding and indexing automatically
    collection.add(
        documents=cs_course_chunks,
        ids=["cs_courses_overview", "cs_courses_54-144", "cs_courses_54-184", "cs_courses_54-281", "cs_courses_54-284", "cs_courses_54-291", "cs_courses_54-384", "cs_courses_54-394", "cs_courses_54-414", "cs_courses_54-424", "cs_courses_54-454", "cs_courses_54-474", "cs_courses_54-514", "cs_courses_54-524", "cs_courses_54-534", "cs_courses_54-644", "cs_courses_54-844", "cs_courses_54-894"],
        metadatas=cs_courses_metadatas
    )

    query = "Which course uses C++"
    # query_embedding = sentence_transformer_ef([query])

    # Query the collection
    results = collection.query(
        query_texts=[query], # Use embedding created by the new embedding function
        n_results=5, # how many results to return
        include=["documents", "metadatas", "distances"]
    )
    print(results)

if __name__ == "__main__":
    main()
