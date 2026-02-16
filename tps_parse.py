import sys, json
d = json.load(sys.stdin)
e = d.get("eval_count", 0)
dur = d.get("eval_duration", 1)
tps = e / (dur / 1e9) if dur else 0
pd = d.get("prompt_eval_duration", 0) / 1e9
td = d.get("total_duration", 0) / 1e9
print(f"Tokens: {e}")
print(f"Eval duration: {dur/1e9:.1f}s")
print(f"TPS: {tps:.2f} tok/s")
print(f"Prompt eval: {pd:.1f}s")
print(f"Total duration: {td:.1f}s")
print(f"Model: {d.get('model','?')}")
