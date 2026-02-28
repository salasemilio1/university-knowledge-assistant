from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    """
    Root route for system. Returns status if call successful.
    :return: Status of system.
    """
    return {"status": "Ok"} # return status

@app.get("retrieve")
def retrieve_response():

    # response = get_response()
    """
    Retrieves JSON response.
    :return:
    """