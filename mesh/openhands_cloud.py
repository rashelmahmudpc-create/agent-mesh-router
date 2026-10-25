"""🖐️ OpenHands Cloud — সরাসরি API দিয়ে কাজ দেওয়া (ওদের সার্ভারে চলে)।

কেন আলাদা ফাইল: `openhands-sdk` বড় প্যাকেজ (Python 3.12+ দরকার)।
তাই import টা **ভেতরে** — বাকি সিস্টেম SDK ছাড়াও চলবে।

ব্যবহার:
    python3 -m mesh.cli --openhands "এই রিপোতে কী কী আছে দেখে বলো"

লাগবে: `OPENHANDS_API_KEY` (ওদের ক্লাউড থেকে), `OPENHANDS_CLOUD_URL` (ঐচ্ছিক)।
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_URL = "https://app.all-hands.dev"
# 🖐️ ওদের ফ্রি টিমে শুধু এই মডেলগুলো চলে (plus লাগালে "team not allowed to access model" আসে)
DEFAULT_MODEL = "openhands/deepseek-v4.1-flash"
MODEL_CANDIDATES = ("openhands/deepseek-v4.1-flash", "openhands/deepseek-v4-flash")
MODEL_DENIED_MARKERS = ("not allowed to access model", "can only access models")


@dataclass
class CloudResult:
    ok: bool
    text: str
    detail: str = ""


def sdk_available() -> bool:
    """openhands-sdk ইনস্টল আছে কি না (import না করেই)।"""
    try:
        import importlib.util

        return importlib.util.find_spec("openhands") is not None
    except Exception:
        return False


def ask(
    message: str,
    api_key: str | None = None,
    cloud_url: str | None = None,
    model: str | None = None,
    sdk_factory=None,
) -> CloudResult:
    """ওদের ক্লাউডে একটা conversation চালিয়ে উত্তর ফেরত দেয়।

    `sdk_factory` টেস্টের জন্য ইনজেক্ট করা যায়।
    """
    api_key = api_key or os.environ.get("OPENHANDS_API_KEY", "").strip()
    cloud_url = cloud_url or os.environ.get("OPENHANDS_CLOUD_URL", DEFAULT_URL)
    model = model or os.environ.get("OPENHANDS_MODEL", DEFAULT_MODEL)

    if not api_key:
        return CloudResult(False, "❌ OPENHANDS_API_KEY নেই — Settings → Secrets এ বসাতে হবে", "no-key")

    if sdk_factory is None:
        if not sdk_available():
            return CloudResult(
                False,
                "❌ openhands-sdk ইনস্টল নেই (Python 3.12+ লাগে)। "
                "`pip install openhands-sdk` — Actions এ ইতিমধ্যে সেটআপ করা আছে।",
                "no-sdk",
            )
        sdk_factory = _default_factory

    # মডেলটা এই টিমের জন্য অনুমোদিত না হলে ("not allowed to access model") পরেরটা চেষ্টা করি
    candidates = [model] + [m for m in MODEL_CANDIDATES if m != model]
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            run = sdk_factory(api_key, cloud_url, candidate)
            text = run(message)
        except Exception as exc:  # noqa: BLE001 — আসল কারণটাই ফেরত দিই
            last_error = exc
            if any(marker in str(exc).lower() for marker in MODEL_DENIED_MARKERS):
                continue  # এই মডেল চলবে না — পরের অনুমোদিত মডেল
            return CloudResult(False, f"❌ OpenHands ক্লাউডে সমস্যা: {type(exc).__name__}: {exc}", "error")

        text = (text or "").strip()
        if not text:
            return CloudResult(False, "❌ OpenHands উত্তর দিল না (খালি আউটপুট)", "empty")
        return CloudResult(True, text)

    return CloudResult(
        False,
        f"❌ OpenHands ক্লাউডে সমস্যা: {type(last_error).__name__}: {last_error}",
        "error",
    )


def _default_factory(api_key: str, cloud_url: str, model: str):
    """SDK দিয়ে একটা callable বানায়: (message) -> উত্তর।

    ⚠️ SDK-র API বদলাতে পারে, তাই প্রতিটা ধাপ আলাদাভাবে ধরা হয়েছে।
    """
    from openhands.sdk import Agent, Conversation, LLM  # type: ignore
    from openhands.workspace.cloud.workspace import OpenHandsCloudWorkspace  # type: ignore

    def run(message: str) -> str:
        llm = LLM(model=model, api_key=api_key)
        agent = Agent(llm=llm)
        with OpenHandsCloudWorkspace(cloud_api_url=cloud_url, cloud_api_key=api_key) as workspace:
            conversation = Conversation(agent=agent, workspace=workspace)
            conversation.send_message(message)
            conversation.run()
            return _last_text(conversation)

    return run


def _last_text(conversation) -> str:
    """conversation থেকে শেষ সহায়ক উত্তরটা বের করার চেষ্টা (SDK সংস্করণভেদে ভিন্ন)।"""
    for attr in ("last_response", "final_response", "response"):
        value = getattr(conversation, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    events = getattr(conversation, "events", None) or []
    for event in reversed(list(events)):
        text = getattr(event, "content", None) or getattr(event, "message", None)
        if isinstance(text, str) and text.strip():
            return text
    return str(conversation)
