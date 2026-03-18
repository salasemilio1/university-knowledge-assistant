from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.post("/chat", response_class=HTMLResponse)
async def chat(message: str = Form(...)):
    # Simulated AI response
    user_msg = f'<div class="message user">{message}</div>'
    bot_msg = f'<div class="message bot">Echo: {message}</div>'
    return user_msg + bot_msg

@app.get("/conversations", response_class=HTMLResponse)
async def conversations():
    return """
    <button hx-get="/load-chat/1" hx-target="#chat-box">Chat 1</button>
    <button hx-get="/load-chat/2" hx-target="#chat-box">Chat 2</button>
    """

@app.get("/new-chat", response_class=HTMLResponse)
async def new_chat():
    return "<p>New chat started.</p>"