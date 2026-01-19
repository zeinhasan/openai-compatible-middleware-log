import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI()

# URL tempat vLLM berjalan (default vLLM)
import os
from dotenv import load_dotenv

load_dotenv() # Load .env file variables

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8005")
PORT = int(os.getenv("PORT", 8004))

# --- 1. Endpoint untuk List Models (GET) ---
@app.get("/v1/models")
async def list_models():
    print(f"\n[LOG] Client meminta list models (/v1/models)... Redirecting to {VLLM_URL}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Forward request ke vLLM
            resp = await client.get(f"{VLLM_URL}/v1/models")
            
            # Kembalikan jawaban persis seperti vLLM
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

# --- 2. Endpoint untuk Chat Completions (POST) ---
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Ambil body dari request user
    body = await request.json()
    
    # --- AREA LOGGING INPUT USER ---
    print("\n" + "="*40)
    print("[LOG] REQUEST CHAT MASUK")
    
    # Log model yang diminta
    if "model" in body:
        print(f"Target Model: {body['model']}")

    # Log pesan user terakhir
    if "messages" in body and len(body['messages']) > 0:
        last_msg = body['messages'][-1]
        print(f"Role: {last_msg.get('role')}")
        print(f"Content: {last_msg.get('content')}")
    else:
        print("Raw Body:", body)
    print("="*40 + "\n")
    # -----------------------------

    # Fungsi generator untuk streaming response
    async def proxy_generator():
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                # Forward request ke vLLM dengan mode stream
                async with client.stream(
                    "POST",
                    f"{VLLM_URL}/v1/chat/completions",
                    json=body,
                    headers=dict(request.headers) # Teruskan headers (seperti Authorization)
                ) as response:
                    
                    if response.status_code != 200:
                        yield f'{{"error": "vLLM Error {response.status_code}"}}'.encode()
                        return

                    # Stream balik output dari vLLM ke Client
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                yield f'{{"error": "{str(e)}"}}'.encode()

    return StreamingResponse(proxy_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    print(f"Wrapper berjalan di port {PORT} -> Forwarding ke {VLLM_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)