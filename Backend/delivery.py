"""
This script serves as the delivery layer of the backend. Its purpose
is to receive a request from the frontend, call core logic and return
data to the frontend.
"""

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    """
    Root route for system. Returns status if call successful.
    :return: Status of system.
    """
    return {"status": "Ok"} # return status

@app.get("/retrieve")
def retrieve_response():
    """
    Retrieves JSON response.
    :return:
    """

   