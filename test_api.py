"""HTTP contract and model reuse checks for the local inference API."""

from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import api


class FakeSession:
    created = 0

    def __init__(self, _path):
        type(self).created += 1
        self.next_letter = 0
        self.ambiguous = False
        self.calls = 0

    def get_inputs(self):
        return [SimpleNamespace(name="image", shape=[None, 96, 96, 3])]

    def get_outputs(self):
        return [SimpleNamespace(name="logits")]

    def run(self, names, inputs):
        assert names == ["logits"]
        assert inputs["image"].shape == (1, 96, 96, 3)
        self.calls += 1
        scores = np.zeros(26, dtype=np.float32)
        if not self.ambiguous:
            scores[self.next_letter] = 10.0
        return [scores[np.newaxis, :]]


class FakeHands:
    def __init__(self, **options):
        assert options["static_image_mode"] is True
        self.hand_present = True

    def process(self, _rgb):
        if not self.hand_present:
            return SimpleNamespace(multi_hand_landmarks=None)
        landmarks = [SimpleNamespace(x=0.2 + (index % 5) * 0.12,
                                     y=0.2 + (index // 5) * 0.12)
                     for index in range(21)]
        return SimpleNamespace(multi_hand_landmarks=[SimpleNamespace(landmark=landmarks)])


class ApiTests(unittest.TestCase):
    def setUp(self):
        FakeSession.created = 0
        self.session_patch = patch.object(api.ort, "InferenceSession", FakeSession)
        self.hands_patch = patch.object(api.mp.solutions.hands, "Hands", FakeHands)
        self.session_patch.start()
        self.hands_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.hands_patch.stop)
        self.service = api.InferenceService()
        self.client = api.create_app(self.service).test_client()
        ok, encoded = cv2.imencode(".jpg", np.full((128, 128, 3), 100, dtype=np.uint8))
        assert ok
        self.image = encoded.tobytes()

    def post_image(self, data=None):
        return self.client.post("/api/v1/predict", data={
            "image": (BytesIO(self.image if data is None else data), "hand.jpg")
        })

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_valid_image(self):
        response = self.post_image()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json), {"letter", "confidence", "timestamp"})
        self.assertIsInstance(response.json["timestamp"], int)

    def test_invalid_image(self):
        response = self.post_image(b"not an image")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "Invalid image")
        self.assertEqual(self.service.session.calls, 0)

    def test_no_hand(self):
        self.service.hands.hand_present = False
        response = self.post_image()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["error"], "No hand detected")
        self.assertEqual(self.service.session.calls, 0)

    def test_a(self):
        response = self.post_image()
        self.assertEqual(response.json["letter"], "A")
        self.assertGreaterEqual(response.json["confidence"], 0.75)

    def test_b(self):
        self.service.session.next_letter = 1
        response = self.post_image()
        self.assertEqual(response.json["letter"], "B")
        self.assertGreaterEqual(response.json["confidence"], 0.75)

    def test_multiple_requests_reuse_model(self):
        for index in (0, 1, 0):
            self.service.session.next_letter = index
            self.assertEqual(self.post_image().status_code, 200)
        self.assertEqual(FakeSession.created, 1)
        self.assertEqual(self.service.session.calls, 3)

    def test_low_confidence(self):
        self.service.session.ambiguous = True
        response = self.post_image()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["error"], "Low confidence")


if __name__ == "__main__":
    unittest.main()
