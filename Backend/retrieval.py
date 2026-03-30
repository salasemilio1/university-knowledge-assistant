"""
This script is the logic core for the retrieval feature. It is called by delivery.
"""

import numpy as np
import chromadb as chroma
import classify
from cli.main import main


def get_response(query:str) -> str:
    """
    Generates a response from a given query.

    Args:
        query(str): The processed query retrieved from delivery.

    Returns:
        str: The response generated from the LLM.
    """

    return "response"