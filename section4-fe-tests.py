from pathlib import Path

root = Path(r"D:\BuiGiaHuy\CN8\EXE202\signify-fe\Signify-FE")
test_path = root / "tests/aiTextUpdate.test.ts"
if test_path.exists():
    raise RuntimeError(f"Refusing to overwrite {test_path}")
source = '''import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAiTextUpdate } from '../src/services/aiTextUpdate.ts';
import { parseAiPrediction } from '../src/services/aiPrediction.ts';

const textEvent = {
  eventId: 'event-1', type: 'AI_TEXT_UPDATE', callId: 42,
  conversationId: 7, text: 'HELLO ', timestamp: 1234,
};

test('parses authoritative text including a trailing space and clear', () => {
  assert.equal(parseAiTextUpdate(JSON.stringify(textEvent), 42)?.text, 'HELLO ');
  assert.equal(parseAiTextUpdate(JSON.stringify({ ...textEvent, text: '' }), 42)?.text, '');
});

test('ignores malformed, unknown, and other-call events safely', () => {
  for (const body of ['not json', '{}', JSON.stringify({ ...textEvent, type: 'UNKNOWN' }),
    JSON.stringify({ ...textEvent, text: 123 }), JSON.stringify({ ...textEvent, callId: 43 })]) {
    assert.equal(parseAiTextUpdate(body, 42), null);
  }
});

test('keeps accepted letter event parser compatible', () => {
  const letter = { eventId: 'event-2', type: 'AI_SIGN_PREDICTION', callId: 42,
    conversationId: 7, letter: 'A', confidence: 0.9, timestamp: 1234 };
  assert.equal(parseAiPrediction(JSON.stringify(letter), 42)?.letter, 'A');
  assert.equal(parseAiTextUpdate(JSON.stringify(letter), 42), null);
  assert.equal(parseAiPrediction(JSON.stringify(textEvent), 42), null);
});
'''
test_path.parent.mkdir(parents=True, exist_ok=True)
test_path.write_bytes(source.replace('\n', '\r\n').encode('utf-8'))

video_path = root / "src/components/VideoCall.tsx"
original = video_path.read_bytes()
old = b"'Khong the cap nhat van ban AI.'"
new = "'Không thể cập nhật văn bản AI.'".encode('utf-8')
if original.count(old) != 1:
    raise RuntimeError("Expected one UI error message")
video_path.write_bytes(original.replace(old, new, 1))
