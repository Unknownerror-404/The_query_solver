from pathlib import Path
from AI_model import CLIP_MODEL_DIR, _load_finetuned_clip, classify_video_proof, extract_video_frames

print("CLIP_MODEL_DIR", CLIP_MODEL_DIR)
print("CLIP exists", Path(CLIP_MODEL_DIR).exists())
print("clip_load", _load_finetuned_clip())
print("empty_video", classify_video_proof(b"not-a-video"))
print("empty_frames", len(extract_video_frames(b"")))
try:
    import cv2
    print("cv2", cv2.__version__)
except Exception as exc:
    print("cv2_error", type(exc).__name__, exc)
