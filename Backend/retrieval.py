"""
This script is the logic core for the retrieval feature. It is called by delivery.
"""

import numpy as np
import chromadb as chroma


def embed_query(query:str) -> np.ndarray:
    """
    Generates embedded query via call to an embedding model.

    Args:
        query(str): The processed query.

    Returns:
        ndarray: The embedded query in the form of a vector.
    """

    return np.random.rand(10)

def embed_query(query:str) -> np.ndarray:
    """
    Generates embedded query via call to an embedding model.

    Args:
        query(str): The processed query.

    Returns:
        ndarray: The embedded query in the form of a vector.
    """

    return np.random.rand(10)

def classify_query():
    """
    Generates embedded query via call to an embedding model.

    Args:

    Returns:
        
    """
    return -1

def similarity_search():
    """
    Performs database search to find relevant document chunks according specifications
    in the embedded query and retrieval plan.

    Args:

    Returns:
    """

    return -1

def rerank():
    """
    Reorders found chunks by the “true” relevance to query.

    Args:

    Returns:
    """

    # likely will be rule based

    return -1

def prompt_LLM():
    """
    Prompts the LLM with the query and other data.

    Args:

    Returns:
    """

    return -1

def get_response(query:str) -> str:
    """
    Generates a response from a given query.

    Args:
        query(str): The processed query retrieved from delivery.

    Returns:
        str: The response generated from the LLM.
    """


    return "response"