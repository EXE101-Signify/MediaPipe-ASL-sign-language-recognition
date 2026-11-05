"""Local HTTP access to the existing single-image ASL inference pipeline.

Run ``python api.py`` and send an image as multipart form field ``image``.
"""

import argparse
import logging
from pathlib import Path
from threading import Lock
from time import monotonic_ns, time_ns

import cv2
from flask import Flask, jsonify, request
import mediapipe as mp
import numpy as np
import onnxruntime as ort

import preprocessing as pp
from realtime_translator import COMMIT_CONFIDENCE


ROOT = Path(__file__).resolve().parent
MAX_IMAGE_BYTES = 10 * 1024 * 1024
logger = logging.getLogger(__name__)


class InferenceService:
    """Keep the model and detector alive while requests remain independent."""

    def __init__(self, model_path=ROOT / "asl_cnn_model.onnx",
                 classes_path=ROOT / "class_names.txt"):
        self.class_names = [name.strip() for name in Path(classes_path).read_text().strip().split(",")]
        self.session = ort.InferenceSession(str(model_path))
        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        self.size = input_meta.shape[1] if isinstance(input_meta.shape[1], int) else pp.MODEL_INPUT_SIZE
        output_names = [output.name for output in self.session.get_outputs()]
        self.output_name = "logits" if "logits" in output_names else output_names[0]
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            model_complexity=pp.HAND_MODEL_COMPLEXITY,
            min_detection_confidence=0.5,
        )
        # MediaPipe Hands is shared, so serialize its process calls. Also keeps
        # session use predictable under Flask's threaded development server.
        self.lock = Lock()

    def predict(self, image_bgr):
        height, width = image_bgr.shape[:2]
        with self.lock:
            result = self.hands.process(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
            if not result.multi_hand_landmarks:
                return None
            _, skeleton_rgb = pp.preprocess_hand(
                result.multi_hand_landmarks[0], width, height, size=self.size
            )
            logits = self.session.run(
                [self.output_name], {self.input_name: pp.model_input(skeleton_rgb)}
            )[0][0]
        # Match the live translator's stable softmax calculation. Each HTTP image
        # is independent, so there is no cross-request rolling score history.
        exponentials = np.exp(logits - np.max(logits))
        scores = exponentials / np.sum(exponentials)
        index = int(np.argmax(scores))
        return self.class_names[index].upper(), float(scores[index])


def create_app(inference=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES
    service = inference if inference is not None else InferenceService()

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/api/v1/predict")
    def predict():
        uploaded = request.files.get("image")
        if uploaded is None:
            return jsonify(error="Missing multipart image field 'image'"), 400

        data = uploaded.read()
        if not data:
            return jsonify(error="Invalid image"), 400
        decode_started = monotonic_ns()
        try:
            image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        finally:
            decode_ms = (monotonic_ns() - decode_started) / 1_000_000
        if image is None or image.size == 0:
            logger.info("ai_prediction decode_ms=%.3f inference_ms=0 outcome=invalid_image", decode_ms)
            return jsonify(error="Invalid image"), 400

        inference_started = monotonic_ns()
        outcome = "error"
        try:
            result = service.predict(image)
            if result is None:
                outcome = "no_hand"
            elif result[1] < COMMIT_CONFIDENCE:
                outcome = "low_confidence"
            else:
                outcome = "success"
        finally:
            inference_ms = (monotonic_ns() - inference_started) / 1_000_000
            logger.info("ai_prediction decode_ms=%.3f inference_ms=%.3f outcome=%s",
                        decode_ms, inference_ms, outcome)
        if result is None:
            return jsonify(error="No hand detected"), 422
        letter, confidence = result
        if confidence < COMMIT_CONFIDENCE:
            return jsonify(error="Low confidence", confidence=confidence), 422
        return jsonify(letter=letter, confidence=confidence, timestamp=time_ns() // 1_000_000)

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="Image exceeds 10 MB limit"), 413

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    create_app().run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
