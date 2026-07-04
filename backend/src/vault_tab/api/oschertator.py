"""Oschertator - 2nd Brain chatbot service with RAG and tool use."""

import json
import os
import re
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..core.graph_index import GraphIndex
from ..core.llm import LLMClient, create_llm_client

router = APIRouter()


def get_vault_root() -> Path:
    return Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/tmp/vibeflow/agent/demo-vault")).resolve()


SYSTEM_PROMPT = """You are Oschertator, a 2nd Brain Assistant with access to the user's Obsidian vault.
You can search notes, read note contents, explore connections, and answer questions based on the vault.
Be concise, helpful, and always cite which notes you're drawing from.
If the user asks something you can't answer from the vault, say so honestly."""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "vault_search",
            "description": "Search vault notes by filename and content. Returns matching notes with snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (filename + full-text search)"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_read",
            "description": "Read the full content of a note by its vault-relative path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Vault-relative path to the markdown file"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph_query",
            "description": "Query the vault graph for nodes and edges. Supports filtering by folder, tag, or search term.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Filter by folder prefix"},
                    "tag": {"type": "string", "description": "Filter by tag"},
                    "q": {"type": "string", "description": "Search query for node titles"},
                    "limit": {"type": "integer", "description": "Max nodes to return (default 400)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "note_backlinks",
            "description": "Get backlinks and outgoing links for a specific note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Vault-relative path to the note"}
                },
                "required": ["path"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: str | dict, vault_root: Path) -> str:
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments or {}

    if not isinstance(args, dict):
        args = {}

    if name == "vault_search":
        return await _tool_search(args.get("query", ""), vault_root)
    elif name == "vault_read":
        return await _tool_read(args.get("path", ""), vault_root)
    elif name == "graph_query":
        return await _tool_graph(args, vault_root)
    elif name == "note_backlinks":
        return await _tool_backlinks(args.get("path", ""), vault_root)
    return f"Unknown tool: {name}"


async def _tool_search(query: str, vault_root: Path) -> str:
    if not query:
        return "No query provided."
    results = []
    ql = query.lower()
    try:
        for md in vault_root.rglob("*.md"):
            title_match = ql in md.name.lower()
            body_match = False
            snippet = ""
            if not title_match:
                try:
                    text = md.read_text(encoding="utf-8", errors="replace")
                    idx_pos = text.lower().find(ql)
                    if idx_pos >= 0:
                        body_match = True
                        start = max(0, idx_pos - 40)
                        end = min(len(text), idx_pos + 60)
                        snippet = text[start:end].replace("\n", " ")
                        if start > 0:
                            snippet = "..." + snippet
                except (OSError, UnicodeDecodeError):
                    continue
            if title_match or body_match:
                results.append({
                    "path": str(md.relative_to(vault_root)),
                    "title": md.name,
                    "title_match": title_match,
                    "snippet": snippet,
                })
    except Exception as e:
        return f"Search error: {e}"
    results.sort(key=lambda r: not r["title_match"])
    return json.dumps(results[:30], ensure_ascii=False)


async def _tool_read(path: str, vault_root: Path) -> str:
    target = (vault_root / path).resolve()
    if not str(target).startswith(str(vault_root)):
        return "Error: path traversal blocked"
    if not target.exists():
        return f"Error: file not found ({path})"
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        return content
    except (OSError, UnicodeDecodeError) as e:
        return f"Error reading file: {e}"


async def _tool_graph(args: dict, vault_root: Path) -> str:
    idx = GraphIndex(vault_root)
    nodes, edges = idx.build()
    folder = args.get("folder", "")
    tag = args.get("tag", "")
    q = args.get("q", "")
    limit = args.get("limit", 400)
    fn, fe = idx.filter(nodes, edges, folder=folder, tag=tag, q=q, limit=limit)
    return json.dumps({
        "nodes": [n.to_dict() for n in fn],
        "edges": [e.to_dict() for e in fe],
        "total_nodes": len(nodes),
        "shown": len(fn),
    }, ensure_ascii=False)


async def _tool_backlinks(path: str, vault_root: Path) -> str:
    idx = GraphIndex(vault_root)
    links = idx.get_note_links(path)
    return json.dumps(links, ensure_ascii=False)


async def _run_llm_with_tools(
    llm: LLMClient,
    messages: list[dict],
    tools: list[dict],
    max_tool_iterations: int = 10,
) -> dict:
    for _ in range(max_tool_iterations):
        result = await llm.chat_with_tools(messages, tools)
        if "error" in result:
            return result
        tool_calls = result.get("tool_calls", [])
        if not tool_calls:
            return result
        vault_root = get_vault_root()
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = tc["function"]["arguments"]
            tool_result = await execute_tool(fn_name, fn_args, vault_root)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })
    return {"error": "Max tool iterations reached"}


async def _stream_llm_with_tools(
    llm: LLMClient,
    user_message: str,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_message}]
    result = None

    for turn in range(10):
        result = await llm.chat_with_tools(messages, TOOLS)
        if "error" in (result or {}):
            yield json.dumps({"delta": f"Error: {(result or {}).get('error', '')}"})
            return
        tool_calls = (result or {}).get("tool_calls", [])
        if not tool_calls:
            break
        vault_root = get_vault_root()
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = tc["function"]["arguments"]
            tool_result = await execute_tool(fn_name, fn_args, vault_root)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})

    if result and result.get("content"):
        yield json.dumps({"delta": result.get("content", "")})
    else:
        yield json.dumps({"delta": ""})


class ChatHistory:
    _histories: dict[str, list[dict]] = {}

    @classmethod
    def get(cls, session_id: str) -> list[dict]:
        return cls._histories.get(session_id, [])

    @classmethod
    def add(cls, session_id: str, message: dict) -> None:
        if session_id not in cls._histories:
            cls._histories[session_id] = []
        cls._histories[session_id].append(message)
        if len(cls._histories[session_id]) > 50:
            cls._histories[session_id] = cls._histories[session_id][-30:]

    @classmethod
    def clear(cls, session_id: str) -> None:
        cls._histories.pop(session_id, None)


@router.post("/v1/chat/completions")
async def chat_completions(body: dict[str, Any]):
    llm_config = {
        "protocol": os.environ.get("LLM_PROTOCOL", "openai-compatible"),
        "base_url": os.environ.get("LLM_ENDPOINT_URL", "http://localhost:8000/v1"),
        "model": os.environ.get("LLM_MODEL", "gpt-4o"),
    }
    llm = create_llm_client(llm_config)

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(400, "messages required")

    session_id = body.get("session_id", "default")
    history = ChatHistory.get(session_id)

    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break

    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + messages
    result = await _run_llm_with_tools(llm, all_messages, TOOLS, max_tool_iterations=10)

    assistant_content = result.get("content", "")
    ChatHistory.add(session_id, {"role": "user", "content": user_msg})
    ChatHistory.add(session_id, {"role": "assistant", "content": assistant_content})

    return {
        "id": f"chatcmpl-{session_id}",
        "object": "chat.completion",
        "model": body.get("model", "oschertator"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": assistant_content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": result.get("tokens_in", 0),
            "completion_tokens": result.get("tokens_out", 0),
            "total_tokens": result.get("tokens_in", 0) + result.get("tokens_out", 0),
        },
    }


@router.post("/v1/chat/stream")
async def chat_stream(body: dict[str, Any]):
    llm_config = {
        "protocol": os.environ.get("LLM_PROTOCOL", "openai-compatible"),
        "base_url": os.environ.get("LLM_ENDPOINT_URL", "http://localhost:8000/v1"),
        "model": os.environ.get("LLM_MODEL", "gpt-4o"),
    }
    llm = create_llm_client(llm_config)

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(400, "messages required")

    session_id = body.get("session_id", "default")
    history = ChatHistory.get(session_id)

    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break

    async def event_generator():
        collected = []
        async for chunk in _stream_llm_with_tools(llm, user_msg, history):
            data = json.loads(chunk)["delta"]
            collected.append(data)
            yield f"data: {json.dumps({'delta': data})}\n\n"
        full_text = "".join(collected)
        ChatHistory.add(session_id, {"role": "user", "content": user_msg})
        ChatHistory.add(session_id, {"role": "assistant", "content": full_text})
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "job_update":
                await websocket.send_json(data)
    except WebSocketDisconnect:
        pass


@router.post("/v1/sessions/clear")
async def clear_session(body: dict[str, Any]):
    session_id = body.get("session_id", "default")
    ChatHistory.clear(session_id)
    return {"cleared": session_id}
