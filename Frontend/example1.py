# FastAPI file to work with example1.html

@app.get("/hello")
def hello():
    return "<p>Hello from FastAPI!</p>"

@app.post("/submit")
def submit(name: str = Form(...)):
    return f"<p>Hello, {name}!</p>"

@app.get("/search")
def search(q: str = ""):
    return "<br>".join([f"Result {i}" for i in range(5) if q.lower() in f"result {i}"])

@app.get("/time")
def time():
    from datetime import datetime
    return f"<p>{datetime.now()}</p>"

@app.delete("/delete/{item_id}")
def delete(item_id: int):
    return ""  # removes element