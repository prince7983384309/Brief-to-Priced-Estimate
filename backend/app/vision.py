"""Computer-vision gem-count estimate: a classical OpenCV baseline (Hough
circles), plus an optional vision-LLM estimate for comparison.
"""
import base64

import cv2
import numpy as np

from app import config


def estimate_gem_count_classical(image_bytes: bytes) -> tuple[int | None, str]:
    """Returns (estimated_count, reason). estimated_count is None only if the
    image can't be decoded (never raises)."""
    try:
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return None, "image could not be decoded"

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.medianBlur(gray, 5)

        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=10,
            param1=50,
            param2=22,
            minRadius=3,
            maxRadius=40,
        )

        if circles is None:
            return 0, "no circular shapes detected"

        count = circles.shape[1]
        return count, f"Hough circle transform detected {count} circular regions"
    except Exception as exc:  # defensive: CV must never crash the request
        return None, f"classical CV failed: {exc}"


def estimate_gem_count_vision_llm(image_bytes: bytes) -> tuple[int | None, str]:
    """Optional comparison point against the classical baseline. Not relied
    upon alone -- only used when VISION_LLM_ENABLED=true."""
    if not config.VISION_LLM_ENABLED:
        return None, "vision-LLM comparison disabled (VISION_LLM_ENABLED=false)"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        completion = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Count the small gems/stones visible on this jewelry "
                                "piece. Respond with ONLY an integer."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                        },
                    ],
                }
            ],
            temperature=0,
        )
        text = completion.choices[0].message.content.strip()
        return int("".join(ch for ch in text if ch.isdigit()) or 0), "vision-LLM estimate"
    except Exception as exc:
        return None, f"vision-LLM call failed: {exc}"
