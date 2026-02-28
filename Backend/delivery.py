"""
This script serves as the delivery layer of the backend. Its purpose
is to receive a request from the frontend, call core logic and return
data to the frontend.
"""

from fastapi import FastAPI
from fastapi import Request
from retrieval import get_response


app = FastAPI()

@app.get("/")
def read_root() -> dict:
    """
    The root route for the system. Returns the system status if the call is successful.
    
    Returns:
        dict: The status of the system.
    """
    return {"status": "Ok"} # return status


@app.get("/retrieve")
def retrieve(request:Request) -> str:
    """
    Retrieves response in string form (later will be streamed).
    
    Returns:
        str: Response from LLM.
    """

    # validate / process input. will depend on format HTMX is configured to send

    return get_response("query")


@app.get("/ingest")
def ingest(request:Request) -> bool:
    """
    Ingests an uploaded document to the database.
    
    Returns:
        bool: Success or failure. For use in frontend error messages.
    """

    # validate / process documents. will depend on format HTMX is configured to send

    return True
