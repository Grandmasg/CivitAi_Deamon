from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import os
import json

SECRET_KEY = "CHANGE_THIS_SECRET"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

app = FastAPI()

# Dummy user for demo
def fake_decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

def get_current_user(token: str = Depends(oauth2_scheme)):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    return user

@app.post("/token")
def login(request: Request):
    # Demo: accepteer elke username/password, geef JWT terug
    data = request.json() if hasattr(request, 'json') else {}
    username = data.get("username", "user")
    token = jwt.encode({"sub": username}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/protected")
def protected_route(user: str = Depends(get_current_user)):
    return {"message": f"Hello, {user}. This is a protected endpoint."}

# WebSocket met JWT-auth
@app.websocket("/ws/downloads")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    user = fake_decode_token(token)
    if not user:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass

# Voeg je routers, daemon, etc. hier toe
