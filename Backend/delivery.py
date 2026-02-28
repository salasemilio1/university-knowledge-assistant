"""
This script serves as the delivery layer of the backend. Its purpose
is to receive a request from the frontend, call core logic and return
data to the frontend.
"""

from fastapi import FastAPI
from retrieval import get_response

app = FastAPI()

@app.get("/")
def read_root() -> dict:
    """
    Root route for system. Returns status if call successful.
    
    Returns:
        dict: The status of the system.
    """
    return {"status": "Ok"} # return status


@app.get("/retrieve")
def retrieve() -> str:
    """
    Retrieves response in string form (later will be streamed).
    
    Returns:
        str: Response from LLM
    """

    return get_response("query")

   