import httpx
import json
import datetime
import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv

# Import custom logger
from logger import logger, configure_logging

# Load .env file variables
load_dotenv()

# Configure logging
configure_logging(log_level="INFO", log_to_console=True)

app = FastAPI()

# URL tempat vLLM berjalan (default vLLM)
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8005")
PORT = int(os.getenv("PORT", 8004))

# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}

# --- 1. Endpoint untuk List Models (GET) ---
@app.get("/v1/models")
async def list_models():
    logger.info(f"Client meminta list models (/v1/models)... Redirecting to {VLLM_URL}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Forward request ke vLLM
            resp = await client.get(f"{VLLM_URL}/v1/models")
            
            # Kembalikan jawaban persis seperti vLLM
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

# --- 2. Endpoint untuk Chat Completions (POST) ---
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Ambil body dari request user
    body = await request.json()
    
    # --- LOGGING ---
    model_name = body.get("model", "unknown")
    log_msg = f"[REQ] Model: {model_name}"
    
    if "messages" in body and len(body['messages']) > 0:
        last_msg = body['messages'][-1]
        role = last_msg.get('role', 'unknown')
        content = last_msg.get('content', '')
        
        # Handle content list (multimodal/structured) or string
        if isinstance(content, list):
             content_str = str(content)
        else:
             content_str = str(content)
        
        # Truncate content for display
        display_content = (content_str[:75] + '...') if len(content_str) > 75 else content_str
        cleaned_content = display_content.replace('\n', ' ')
        log_msg += f" | {role}: {cleaned_content}"
    else:
        log_msg += f" | Raw: {str(body)[:50]}..."

    logger.info(log_msg)
    # ---------------

    # Cek apakah client meminta streaming
    is_stream = body.get("stream", False)
    
    # --- SANITIZE HEADERS ---
    # Hanya kirim Authorization header. Content-Type akan otomatis diset library httpx saat pakai parameter json=...
    outbound_headers = {}
    if "authorization" in request.headers:
        outbound_headers["Authorization"] = request.headers["authorization"]

    target_url = f"{VLLM_URL}/v1/chat/completions"
    
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            if is_stream:
                # --- HANDLING STREAMING ---
                # Fungsi generator untuk streaming response
                async def proxy_generator():
                    collected_content = []
                    async with httpx.AsyncClient(timeout=None) as stream_client:
                        try:
                            # Use stream context manager properly
                            async with stream_client.stream(
                                "POST",
                                target_url,
                                json=body,
                                headers=outbound_headers
                            ) as response:
                                
                                if response.status_code != 200:
                                    err_content = await response.aread()
                                    err_text = err_content.decode('utf-8')
                                    logger.error(f"vLLM responded with {response.status_code} - {err_text}")
                                    yield err_content
                                    return

                                # Stream balik output dari vLLM ke Client
                                async for chunk in response.aiter_bytes():
                                    yield chunk
                                    
                                    # Process chunk for logging (Non-blocking attempt)
                                    try:
                                        chunk_str = chunk.decode("utf-8")
                                        lines = chunk_str.split('\n')
                                        for line in lines:
                                            if line.startswith("data: ") and not line.strip().endswith("[DONE]"):
                                                json_str = line[6:] # Skip "data: "
                                                if json_str.strip():
                                                    data = json.loads(json_str)
                                                    delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                                    if delta:
                                                        collected_content.append(delta)
                                    except:
                                        pass # Ignore parse errors during stream
                            
                            # Log accumulated response
                            full_reply = "".join(collected_content)
                            cleaned_reply = full_reply.replace('\n', ' ')
                            display_reply = (cleaned_reply[:100] + '...') if len(cleaned_reply) > 100 else cleaned_reply
                            logger.info(f"[RESP] {display_reply}")

                        except Exception as e:
                            logger.error(f"Stream Exception: {e}")
                            yield f'{{"error": "{str(e)}"}}'.encode()
                            
                return StreamingResponse(proxy_generator(), media_type="text/event-stream")
            
            else:
                # --- HANDLING NON-STREAMING (NORMAL) ---
                logger.info("Mode: Non-Streaming")
                response = await client.post(
                    target_url,
                    json=body,
                    headers=outbound_headers
                )
                
                if response.status_code != 200:
                    logger.error(f"vLLM Error: {response.status_code} - {response.text}")
                    return JSONResponse(content={"error": f"vLLM Error {response.status_code}", "details": response.text}, status_code=response.status_code)

                # Log response
                resp_json = response.json()
                try:
                    ai_content = resp_json['choices'][0]['message']['content']
                except:
                    ai_content = str(resp_json)
                
                # Clean content
                if isinstance(ai_content, str):
                    cleaned_resp = ai_content.replace('\n', ' ')
                else:
                    cleaned_resp = str(ai_content)
                    
                display_resp = (cleaned_resp[:100] + '...') if len(cleaned_resp) > 100 else cleaned_resp
                
                logger.info(f"[RESP] {display_resp}") 
                
                return JSONResponse(content=resp_json, status_code=response.status_code)
                
        except Exception as e:
            logger.error(f"Exception: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Wrapper berjalan di port {PORT} -> Forwarding ke {VLLM_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)