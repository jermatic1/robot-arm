"""Camera previews as MJPEG, which the TV's WebView plays in a plain <img>."""

import asyncio
from collections.abc import AsyncIterator, Callable

import cv2
import numpy as np

FPS = 10
BLANK = np.full((480, 640, 3), 30, dtype=np.uint8)


def jpeg(frame: np.ndarray) -> bytes:
    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    ok, data = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return data.tobytes() if ok else b""


async def mjpeg(
    get_frame: Callable[[], np.ndarray | None], disconnected: Callable
) -> AsyncIterator[bytes]:
    while not await disconnected():
        frame = get_frame()
        body = jpeg(BLANK if frame is None else frame)
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + body + b"\r\n"
        await asyncio.sleep(1 / FPS)
