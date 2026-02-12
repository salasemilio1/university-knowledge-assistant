import chromadb

def md_to_string(file_path):
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