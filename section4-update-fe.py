from pathlib import Path

root = Path(r"D:\BuiGiaHuy\CN8\EXE202\signify-fe\Signify-FE\src")

stream = '''import { parseAiPrediction, type AiPredictionEvent } from './aiPrediction';
import { parseAiTextUpdate, type AiTextUpdateEvent } from './aiTextUpdate';
import { subscribeToStomp, type StompConnectionState } from './stompConnection';

export type AiConnectionState = StompConnectionState;

export function subscribeToAiCallEvents(
  callId: number,
  onPrediction: (prediction: AiPredictionEvent) => void,
  onTextUpdate: (update: AiTextUpdateEvent) => void,
  onStateChange: (state: AiConnectionState) => void,
): () => void {
  if (!Number.isSafeInteger(callId) || callId <= 0) return () => {};
  return subscribeToStomp(`/user/queue/calls/${callId}`, (body) => {
    const prediction = parseAiPrediction(body, callId);
    if (prediction) {
      onPrediction(prediction);
      return;
    }
    const update = parseAiTextUpdate(body, callId);
    if (update) onTextUpdate(update);
  }, onStateChange);
}
'''

text_event = '''export interface AiTextUpdateEvent {
  eventId: string;
  type: 'AI_TEXT_UPDATE';
  callId: number;
  conversationId: number;
  text: string;
  timestamp: number;
}

export function parseAiTextUpdate(body: string, currentCallId: number): AiTextUpdateEvent | null {
  try {
    const event: unknown = JSON.parse(body);
    if (typeof event !== 'object' || event === null) return null;
    const value = event as Record<string, unknown>;
    if (value.type !== 'AI_TEXT_UPDATE' || value.callId !== currentCallId) return null;
    if (typeof value.eventId !== 'string' || !value.eventId) return null;
    if (!Number.isSafeInteger(value.conversationId) || Number(value.conversationId) <= 0) return null;
    if (typeof value.text !== 'string' || !/^[A-Z ]*$/.test(value.text)) return null;
    if (!Number.isSafeInteger(value.timestamp) || Number(value.timestamp) <= 0) return null;
    return value as unknown as AiTextUpdateEvent;
  } catch {
    return null;
  }
}
'''

text_api = '''import { apiFetch } from './apiClient';
import { parseAiTextUpdate, type AiTextUpdateEvent } from './aiTextUpdate';

export type AiTextCommand = 'space' | 'delete' | 'clear';

export async function sendAiTextCommand(callId: number, command: AiTextCommand): Promise<AiTextUpdateEvent> {
  const response = await apiFetch<AiTextUpdateEvent>(`/api/calls/${callId}/text/${command}`, { method: 'POST' });
  const update = parseAiTextUpdate(JSON.stringify(response.data), callId);
  if (!update) throw new Error('Phản hồi văn bản AI không hợp lệ.');
  return update;
}
'''

video_path = root / "components/VideoCall.tsx"
video = video_path.read_bytes()
changes = [
    (b"import { subscribeToAiPredictions, type AiConnectionState } from '../services/aiPredictionStream';",
     b"import { subscribeToAiCallEvents, type AiConnectionState } from '../services/aiPredictionStream';\r\nimport { sendAiTextCommand, type AiTextCommand } from '../services/aiTextApi';"),
    (b"  const [latestPrediction, setLatestPrediction] = useState<AiPredictionEvent | null>(null);",
     b"  const [latestPrediction, setLatestPrediction] = useState<AiPredictionEvent | null>(null);\r\n  const [aiText, setAiText] = useState<string | null>(null);\r\n  const [textActionBusy, setTextActionBusy] = useState(false);\r\n  const [textActionError, setTextActionError] = useState<string | null>(null);"),
    (b"    setLatestPrediction(null);\r\n    if (call.status !== 'ACCEPTED'",
     b"    setLatestPrediction(null);\r\n    setAiText(null);\r\n    setTextActionError(null);\r\n    if (call.status !== 'ACCEPTED'"),
    (b"    return subscribeToAiPredictions(callId, (prediction) => {",
     b"    return subscribeToAiCallEvents(callId, (prediction) => {"),
    (b"      });\r\n    }, setAiConnectionState);",
     b"      });\r\n    }, (update) => setAiText(update.text), setAiConnectionState);"),
    (b"  const performCallAction = async (action: 'accept' | 'reject' | 'end') => {",
     b"  const performTextAction = async (command: AiTextCommand) => {\r\n    if (role !== 'SIGNER' || call.status !== 'ACCEPTED' || textActionBusy) return;\r\n    setTextActionBusy(true);\r\n    setTextActionError(null);\r\n    try {\r\n      await sendAiTextCommand(callId, command);\r\n    } catch (error) {\r\n      setTextActionError(error instanceof Error ? error.message : 'Khong the cap nhat van ban AI.');\r\n    } finally {\r\n      setTextActionBusy(false);\r\n    }\r\n  };\r\n\r\n  const performCallAction = async (action: 'accept' | 'reject' | 'end') => {"),
    (b"className=\"font-extrabold tracking-wide leading-relaxed\">\r\n                \"{latestPrediction?.letter ?? (currentSubtitle || '",
     b"className=\"font-extrabold tracking-wide leading-relaxed whitespace-pre-wrap\">\r\n                \"{call.status === 'ACCEPTED' ? (aiText !== null ? (aiText || 'Dang cho nhan dien') : (currentSubtitle || '"),
]

for old, new in changes[:5]:
    if video.count(old) != 1:
        raise RuntimeError(f"Expected one VideoCall match: {old!r}")
    video = video.replace(old, new, 1)

old = b"  const performCallAction = async (action: 'accept' | 'reject' | 'end') => {"
new = changes[5][1]
if video.count(old) != 1:
    raise RuntimeError("Expected one call action match")
video = video.replace(old, new, 1)

old_subtitle = b"\"{latestPrediction?.letter ?? (currentSubtitle || '" + 'Đang chờ nhận diện'.encode() + b"')}\""
new_subtitle = b"\"{call.status === 'ACCEPTED' ? (aiText !== null ? (aiText || '" + 'Đang chờ nhận diện'.encode() + b"') : (currentSubtitle || '" + 'Đang chờ nhận diện'.encode() + b"')) : '" + 'Đang chờ nhận diện'.encode() + b"'}\""
if video.count(old_subtitle) != 1:
    raise RuntimeError("Expected one subtitle match")
video = video.replace(old_subtitle, new_subtitle, 1)

old_class = b'className="font-extrabold tracking-wide leading-relaxed"'
if video.count(old_class) != 1:
    raise RuntimeError("Expected one subtitle class match")
video = video.replace(old_class, b'className="font-extrabold tracking-wide leading-relaxed whitespace-pre-wrap"', 1)

needle = b"          <div className=\"flex items-center gap-2\">\r\n            {/* Subtitles custom control */}"
controls = '''          {role === 'SIGNER' && call.status === 'ACCEPTED' && (
            <div className="flex flex-wrap items-center gap-2" aria-label="Điều khiển văn bản AI">
              {(['space', 'delete', 'clear'] as const).map((command) => (
                <button
                  key={command}
                  type="button"
                  disabled={textActionBusy}
                  onClick={() => void performTextAction(command)}
                  className="rounded-xl bg-neutral-900 px-3 py-2 text-xs font-bold text-white hover:bg-neutral-800 disabled:opacity-50"
                >
                  {command.toUpperCase()}
                </button>
              ))}
              {textActionError && <span role="alert" className="text-xs text-red-300">{textActionError}</span>}
            </div>
          )}

'''.replace('\n', '\r\n').encode('utf-8')
if video.count(needle) != 1:
    raise RuntimeError("Expected one toolbar insertion point")
video = video.replace(needle, controls + needle, 1)

files = {
    root / "services/aiPredictionStream.ts": stream,
    root / "services/aiTextUpdate.ts": text_event,
    root / "services/aiTextApi.ts": text_api,
}

for path in (root / "services/aiTextUpdate.ts", root / "services/aiTextApi.ts"):
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing file: {path}")

video_path.write_bytes(video)
for path, content in files.items():
    path.write_bytes(content.replace('\n', '\r\n').encode('utf-8'))
