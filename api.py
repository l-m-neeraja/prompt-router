"""
Simple FastAPI web API for the prompt router.
Provides transparency by returning intent and confidence alongside the response.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import classify_intent, process_message, route_and_respond

app = FastAPI(
    title="LLM Prompt Router",
    description="Intent-based routing to specialized AI personas",
    version="1.0.0",
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    intent: str
    confidence: float
    response: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Process a message and return the response with intent metadata."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    intent_result = classify_intent(request.message)
    final_response = route_and_respond(request.message, intent_result)

    # Log (import and call from app)
    from app import log_route

    log_route(
        intent=intent_result["intent"],
        confidence=intent_result["confidence"],
        user_message=request.message,
        final_response=final_response,
    )

    return ChatResponse(
        intent=intent_result["intent"],
        confidence=intent_result["confidence"],
        response=final_response,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
