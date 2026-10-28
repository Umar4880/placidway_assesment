"""
Chat route handling user queries, conversational streaming, and responses.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.orchestration.schemas import ChatRequest, ChatResponse
from src.orchestration.service import get_orchestration_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Handle a user conversation turn synchronously.
    Returns the complete ChatResponse.
    """
    try:
        service = get_orchestration_service()
        response = await service.chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Handle a user conversation turn via Server-Sent Events (SSE) streaming.
    Streams token deltas in real-time followed by a final completion metadata event.
    """
    try:
        service = get_orchestration_service()
        return StreamingResponse(
            service.chat_stream(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
