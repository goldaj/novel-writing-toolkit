"""Extract visible user/assistant messages from public ChatGPT share pages.

The current share page embeds a React Router turbo-stream payload.  This
script decodes that payload without using or modifying the originating chats.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

import requests


ENQUEUE_RE = re.compile(
    r'window\.__reactRouterContext\.streamController\.enqueue\(("(?:\\.|[^"\\])*")\);</script>',
    re.DOTALL,
)


def _decode_flat_payload(flat: list[Any]) -> Any:
    cache: dict[int, Any] = {}

    def hydrate(ref: Any) -> Any:
        if not isinstance(ref, int):
            return ref
        if ref < 0:
            # Turbo-stream/devalue special sentinels are irrelevant to the
            # visible conversation. Treat them as absent.
            return None
        if ref in cache:
            return cache[ref]
        if ref >= len(flat):
            return None

        value = flat[ref]
        if value is None or isinstance(value, (str, int, float, bool)):
            cache[ref] = value
            return value
        if isinstance(value, list):
            result: list[Any] = []
            cache[ref] = result
            result.extend(hydrate(item) for item in value)
            return result
        if isinstance(value, dict):
            result_dict: dict[str, Any] = {}
            cache[ref] = result_dict
            for encoded_key, encoded_value in value.items():
                if encoded_key.startswith("_") and encoded_key[1:].lstrip("-").isdigit():
                    key = hydrate(int(encoded_key[1:]))
                else:
                    key = encoded_key
                result_dict[str(key)] = hydrate(encoded_value)
            return result_dict
        return value

    return hydrate(0)


def fetch_shared_conversation(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=90)
    response.raise_for_status()

    match = ENQUEUE_RE.search(response.text)
    if not match:
        raise RuntimeError(f"No embedded conversation payload found at {url}")

    stream_text = json.loads(match.group(1))
    flat = json.loads(stream_text)
    root = _decode_flat_payload(flat)
    route = root["loaderData"]["routes/share.$shareId.($action)"]
    return route["serverResponse"]["data"]


def content_to_text(content: Any) -> str:
    if not isinstance(content, dict):
        return ""

    parts = content.get("parts")
    if isinstance(parts, list):
        rendered: list[str] = []
        for part in parts:
            if isinstance(part, str):
                rendered.append(part)
            elif isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    rendered.append(part["text"])
                elif isinstance(part.get("content"), str):
                    rendered.append(part["content"])
        return "\n".join(piece for piece in rendered if piece)

    text = content.get("text")
    return text if isinstance(text, str) else ""


def visible_messages(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in conversation.get("linear_conversation", []):
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        metadata = message.get("metadata") or {}
        if metadata.get("is_visually_hidden_from_conversation"):
            continue
        author = message.get("author") or {}
        role = author.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = content_to_text(message.get("content"))
        if not text.strip():
            continue
        result.append(
            {
                "id": message.get("id"),
                "role": role,
                "create_time": message.get("create_time"),
                "text": html.unescape(text).strip(),
                "attachments": metadata.get("attachments") or [],
            }
        )
    return result


def render_text(conversation: dict[str, Any], source_url: str) -> str:
    messages = visible_messages(conversation)
    lines = [
        f"TITRE : {conversation.get('title', '')}",
        f"SOURCE : {source_url}",
        f"MESSAGES VISIBLES : {len(messages)}",
        "",
    ]
    for index, message in enumerate(messages, 1):
        lines.append("=" * 78)
        lines.append(f"MESSAGE {index:03d} — {message['role'].upper()}")
        attachments = message.get("attachments") or []
        if attachments:
            names = [
                attachment.get("name", "")
                for attachment in attachments
                if isinstance(attachment, dict) and attachment.get("name")
            ]
            if names:
                lines.append("PIÈCES JOINTES : " + " | ".join(names))
        lines.append("=" * 78)
        lines.append(message["text"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("urls", nargs="+")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []

    for index, url in enumerate(args.urls, 1):
        conversation = fetch_shared_conversation(url)
        messages = visible_messages(conversation)
        output_path = args.output_dir / f"conversation_{index}.txt"
        output_path.write_text(render_text(conversation, url), encoding="utf-8")
        manifest.append(
            {
                "index": index,
                "title": conversation.get("title"),
                "url": url,
                "visible_messages": len(messages),
                "characters": sum(len(message["text"]) for message in messages),
                "output": str(output_path),
            }
        )

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
