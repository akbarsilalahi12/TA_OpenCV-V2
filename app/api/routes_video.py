"""
Route /video_feed (MJPEG stream).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.frame_broadcaster import mjpeg_generator


router = APIRouter(tags=["video"])


@router.get("/video_feed")
def video_feed(request: Request):
    loop = request.app.state.detection_loop
    return StreamingResponse(
        mjpeg_generator(loop, fps=15),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
