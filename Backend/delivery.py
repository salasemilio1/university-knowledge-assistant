"""
This script serves as the delivery layer of the backend. Its purpose
is to receive a request from the frontend, call core logic and return
data to the frontend.
"""

from fastapi import FastAPI, Request, HTTPException
from cli.main import retrieve_response
from ingestion import ingest_document


app = FastAPI()

@app.get("/")
def read_root() -> dict:
    """
    The root route for the system. Returns the system status if the call is successful.
    
    Returns:
        dict: The status of the system.
    """
    return {"status": "Ok"} # return status


@app.post("/retrieve")
def retrieve(request:Request) -> str:
    """
    Retrieves response in string form (later will be streamed).
    Assumes form data.
    
    Returns:
        str: Response from LLM.
    """

    form = request.form()
    query:str = form["query"]

    # check for query existence and type

    if query == None:
        raise HTTPException(status_code=400, detail="Missing \"query\" field.")
    
    if not isinstance(query, str):
        raise HTTPException(status_code=400, detail="\"Query\" field must be a String.")

    # remove whitespace
    query = query.strip()

    return get_response(query)
