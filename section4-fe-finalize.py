from pathlib import Path

path = Path(r"D:\BuiGiaHuy\CN8\EXE202\signify-fe\Signify-FE\src\components\VideoCall.tsx")
data = path.read_bytes()
old = '''    return subscribeToAiCallEvents(callId, (prediction) => {
      if (import.meta.env.DEV) console.debug('[AI] STOMP prediction received');
      setLatestPrediction(() => {
        if (import.meta.env.DEV) console.debug(`[AI] Subtitle updated: ${prediction.letter}`);
        return prediction;
      });
    }, (update) => setAiText(update.text), setAiConnectionState);
'''.replace('\n', '\r\n').encode('utf-8')
new = '''    let active = true;
    const unsubscribe = subscribeToAiCallEvents(callId, (prediction) => {
      if (!active) return;
      if (import.meta.env.DEV) console.debug(`[AI] Accepted letter: ${prediction.letter}`);
      setLatestPrediction(prediction);
    }, (update) => {
      if (active) setAiText(update.text);
    }, setAiConnectionState);
    return () => {
      active = false;
      unsubscribe();
    };
'''.replace('\n', '\r\n').encode('utf-8')
if data.count(old) != 1:
    raise RuntimeError('Expected one AI subscription effect')
path.write_bytes(data.replace(old, new, 1))
