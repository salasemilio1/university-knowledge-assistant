"""
This script is the logic core for the retrieval feature. It is called by delivery.
"""

import numpy as np


def get_response(query:str) -> str:
    """
    Generates a response from a given query.

    Args:
        query(str): The processed query retrieved from delivery.

    Returns:
        str: The response generated from the LLM (will be a stream in future).
    """

    return "response"

def embed_query(query:str) -> np.ndarray:
    """
    Generates embedded query via call to an embedding model.

    Args:
        query(str): The processed query.

    Returns:
        ndarray: The embedded query in the form of a vector.
    """

    return np.random.rand(10)