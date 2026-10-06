from pathlib import Path

root = Path(r"D:\BuiGiaHuy\CN8\EXE202\signify-fe\Signify-FE\src")
replacements = {
    "services/aiFrameApi.ts": [
        (b"Promise<AiPredictionEvent> {", b"Promise<AiPredictionEvent | null> {"),
        (b"  const prediction = response.data;", b"  if (response.status === 204) return null;\r\n  const prediction = response.data;"),
    ],
    "hooks/useAiFrameCapture.ts": [
        (b"if (import.meta.env.DEV) console.debug(`[AI] Prediction received: ${prediction.letter} ${prediction.confidence.toFixed(2)}`);",
         b"if (prediction && import.meta.env.DEV) console.debug(`[AI] Accepted letter: ${prediction.letter} ${prediction.confidence.toFixed(2)}`);"),
    ],
    "components/VideoCall.tsx": [
        (b"setLatestPrediction((previous) => {", b"setLatestPrediction(() => {"),
        (b"        if (previous?.letter === prediction.letter && Math.abs(previous.confidence - prediction.confidence) < 0.05) return previous;\r\n", b""),
    ],
}

updates = []
for relative, changes in replacements.items():
    path = root / relative
    original = path.read_bytes()
    updated = original
    for old, new in changes:
        if updated.count(old) != 1:
            raise RuntimeError(f"Expected one match in {path}: {old!r}")
        updated = updated.replace(old, new, 1)
    updates.append((path, updated))

for path, updated in updates:
    path.write_bytes(updated)
