import sys
import time

from services.gemini_service import _gemini_api_keys, get_gemini_model


def mask_key(key: str) -> str:
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return key
    return f"{key[:6]}...{key[-4:]}"


def main() -> int:
    keys = _gemini_api_keys()
    if not keys:
        print("No Gemini API keys found in environment.")
        return 1

    print(f"Found {len(keys)} Gemini keys. Testing each key...")
    print("-" * 60)

    ok = 0
    failed = 0

    for i, key in enumerate(keys, start=1):
        label = f"KEY-{i} ({mask_key(key)})"
        try:
            model = get_gemini_model(key)
            response = model.generate_content("Reply with exactly: OK")
            text = (getattr(response, "text", "") or "").strip()
            if text:
                print(f"[PASS] {label} -> {text[:80]}")
            else:
                print(f"[PASS] {label} -> Received empty text but request succeeded")
            ok += 1
        except Exception as e:
            msg = str(e).replace("\n", " ")
            print(f"[FAIL] {label} -> {msg[:220]}")
            failed += 1

        time.sleep(1.2)

    print("-" * 60)
    print(f"Result: {ok} passed, {failed} failed")

    return 0 if ok > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
