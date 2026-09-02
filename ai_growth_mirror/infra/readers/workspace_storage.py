"""Shared parser for VS Code-style workspaceStorage chat sessions."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from ...domain.session.model import SessionRecord
from ...domain.signals.tooling import compute_tier_counts
from .base import BaseSessionAdapter, SessionRef, SUBAGENT_TOOL_NAMES, _max_mtime, detect_language, parse_iso, parse_ts


_SESSION_DIR_CANDIDATES = (
    Path("chatSessions"),
    Path("GitHub.copilot-chat") / "transcripts",
)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


class WorkspaceStorageChatAdapter(BaseSessionAdapter):
    """Base adapter for tools that persist chatSessions under workspaceStorage."""

    session_dir_candidates = _SESSION_DIR_CANDIDATES

    def extra_storage_roots(self) -> list[Path]:
        return []

    def _quick_extract_project_path(self, raw: SessionRef) -> str:
        workspace_json = next((path for path in raw.source_paths if path.name == "workspace.json"), None)
        if workspace_json and workspace_json.exists():
            try:
                with open(workspace_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                folder = data.get("folder", "")
                if folder.startswith("file:///"):
                    folder = folder[8:]
                return folder
            except Exception:
                pass
        return ""

    def is_available(self) -> bool:
        return any(self._iter_session_files())

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        for session_file, workspace_dir in self._iter_session_files():
            start_time = self._read_session_start_time(session_file)
            source_paths = [session_file]
            workspace_json = workspace_dir / "workspace.json"
            if workspace_json.exists():
                source_paths.append(workspace_json)
            yield SessionRef(
                session_id=session_file.stem,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=source_paths,
                source_mtime=_max_mtime(source_paths),
            )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        session_file = raw.source_paths[0]
        workspace_json = next((path for path in raw.source_paths if path.name == "workspace.json"), None)
        workspace = self._load_workspace_meta(workspace_json)
        state = self._load_session_state(session_file)
        requests = list(state.get("requests") or [])
        tool_counts: Counter[str] = Counter()
        file_paths: set[str] = set()
        languages: Counter[str] = Counter()
        user_count = 0
        assistant_count = 0
        first_prompt = ""
        top_user_messages: list[str] = []

        for request in requests:
            if not isinstance(request, dict):
                continue
            user_text = self._extract_user_text(request.get("message"))
            if user_text:
                user_count += 1
                if not first_prompt:
                    first_prompt = user_text[:500]
                if len(top_user_messages) < 5:
                    top_user_messages.append(user_text[:300])
            assistant_text = self._extract_assistant_text(request.get("response"))
            if assistant_text:
                assistant_count += 1
            self._collect_response_signals(request.get("response"), tool_counts, file_paths)
            self._collect_response_signals(request.get("message"), tool_counts, file_paths)

        for file_path in file_paths:
            lang = detect_language(file_path)
            if lang:
                languages[lang] += 1

        end_time = self._file_mtime_iso(session_file)
        models_used = sorted({model for model in self._extract_models(state) if model})
        tool_count_dict = dict(tool_counts)
        uses_subagent = any(name in SUBAGENT_TOOL_NAMES for name in tool_count_dict)
        uses_mcp = any("mcp" in name for name in tool_count_dict)
        uses_web_search = "web_search" in tool_count_dict or "browser_search" in tool_count_dict
        uses_web_fetch = "web_fetch" in tool_count_dict or "browser_fetch" in tool_count_dict

        return SessionRecord(
            session_id=state.get("sessionId") or raw.session_id,
            tool_name=self.tool_name,
            project_path=workspace.get("project_path", ""),
            git_branch=None,
            start_time=raw.start_time.isoformat(),
            end_time=end_time,
            duration_minutes=self._duration_minutes(raw.start_time, end_time),
            first_prompt=first_prompt,
            user_message_count=user_count,
            assistant_message_count=assistant_count,
            tool_counts=tool_count_dict,
            tool_tier_counts=compute_tier_counts(tool_count_dict),
            files_modified=len(file_paths),
            languages=dict(languages),
            top_user_messages=top_user_messages,
            uses_subagent=uses_subagent,
            uses_mcp=uses_mcp,
            uses_web_search=uses_web_search,
            uses_web_fetch=uses_web_fetch,
            models_used=models_used,
        )

    def _storage_roots(self) -> list[Path]:
        candidates = list(self.data_roots) + self.extra_storage_roots()
        resolved: list[Path] = []
        for root in _dedupe_paths(candidates):
            if root.name == "workspaceStorage":
                resolved.append(root)
            resolved.append(root / "User" / "workspaceStorage")
            resolved.append(root / "workspaceStorage")
        return _dedupe_paths(resolved)

    def _iter_workspace_dirs(self) -> Iterator[Path]:
        seen: set[str] = set()
        for storage_root in self._storage_roots():
            if not storage_root.exists():
                continue
            for child in sorted(storage_root.iterdir()):
                if not child.is_dir():
                    continue
                key = str(child).lower()
                if key in seen:
                    continue
                seen.add(key)
                yield child

    def _iter_session_files(self) -> Iterator[tuple[Path, Path]]:
        for workspace_dir in self._iter_workspace_dirs():
            for rel_dir in self.session_dir_candidates:
                sessions_dir = workspace_dir / rel_dir
                if not sessions_dir.exists():
                    continue
                for path in sorted(sessions_dir.glob("*.json*")):
                    if path.is_file():
                        yield path, workspace_dir

    @staticmethod
    def _read_session_start_time(session_file: Path) -> datetime:
        state = WorkspaceStorageChatAdapter._load_session_state(session_file)
        ts_raw = state.get("creationDate") or state.get("createdAt") or state.get("timestamp")
        if ts_raw:
            try:
                parsed = parse_ts(ts_raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except Exception:
                pass
        try:
            return datetime.fromtimestamp(session_file.stat().st_ctime, tz=timezone.utc)
        except OSError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _load_workspace_meta(workspace_json: Optional[Path]) -> dict[str, Any]:
        if workspace_json is None or not workspace_json.exists():
            return {"project_path": ""}
        try:
            data = json.loads(workspace_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"project_path": ""}
        folder = data.get("folder")
        if isinstance(folder, str):
            return {"project_path": folder}
        workspace = data.get("workspace")
        if isinstance(workspace, dict):
            config = workspace.get("configPath")
            if isinstance(config, str):
                return {"project_path": config}
        return {"project_path": ""}

    @staticmethod
    def _load_session_state(session_file: Path) -> dict[str, Any]:
        if session_file.suffix.lower() == ".json":
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data.get("v", data)
            except (OSError, json.JSONDecodeError):
                return {}
            return {}

        state: dict[str, Any] = {"sessionId": session_file.stem, "requests": []}
        try:
            with open(session_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    kind = entry.get("kind")
                    if kind == 0 and isinstance(entry.get("v"), dict):
                        base = entry["v"]
                        state.update({k: v for k, v in base.items() if k != "requests"})
                        if isinstance(base.get("requests"), list):
                            state["requests"] = list(base["requests"])
                    elif kind == 1 and entry.get("k") == ["customTitle"] and isinstance(entry.get("v"), str):
                        state["customTitle"] = entry["v"]
                    elif kind == 2 and entry.get("k") == ["requests"] and isinstance(entry.get("v"), list):
                        state.setdefault("requests", []).extend(entry["v"])
        except OSError:
            return {}
        return state

    @staticmethod
    def _extract_text_blocks(value: Any) -> str:
        chunks: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, str):
                if node.strip():
                    chunks.append(node.strip())
                return
            if isinstance(node, list):
                for item in node:
                    walk(item)
                return
            if isinstance(node, dict):
                preferred = (
                    "text",
                    "message",
                    "content",
                    "body",
                    "markdown",
                    "value",
                    "response",
                )
                for key in preferred:
                    if key in node:
                        walk(node[key])
                return

        walk(value)
        return "\n".join(dict.fromkeys(chunks)).strip()

    @classmethod
    def _extract_user_text(cls, value: Any) -> str:
        return cls._extract_text_blocks(value)

    @classmethod
    def _extract_assistant_text(cls, value: Any) -> str:
        return cls._extract_text_blocks(value)

    @classmethod
    def _collect_response_signals(
        cls,
        value: Any,
        tool_counts: Counter[str],
        file_paths: set[str],
    ) -> None:
        if isinstance(value, list):
            for item in value:
                cls._collect_response_signals(item, tool_counts, file_paths)
            return
        if not isinstance(value, dict):
            return

        path_value = value.get("path") or value.get("filePath") or value.get("uri")
        if isinstance(path_value, str) and path_value:
            file_paths.add(path_value)

        tool_name = value.get("toolName")
        if isinstance(tool_name, str) and tool_name:
            tool_counts[tool_name.strip().lower()] += 1
        else:
            name = value.get("name")
            marker = str(value.get("kind") or value.get("type") or "").lower()
            if isinstance(name, str) and name and ("tool" in marker or "invocation" in marker or "toolCallId" in value):
                tool_counts[name.strip().lower()] += 1

        for child in value.values():
            cls._collect_response_signals(child, tool_counts, file_paths)

    @staticmethod
    def _extract_models(state: dict[str, Any]) -> list[str]:
        models: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                for key, val in node.items():
                    if key.lower() == "model" and isinstance(val, str) and val.strip():
                        models.add(val.strip())
                    else:
                        walk(val)

        walk(state)
        return sorted(models)

    @staticmethod
    def _file_mtime_iso(path: Path) -> Optional[str]:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            return None

    @staticmethod
    def _duration_minutes(start_time: datetime, end_time_iso: Optional[str]) -> Optional[int]:
        if not end_time_iso:
            return None
        try:
            end_dt = parse_iso(end_time_iso)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            return max(int((end_dt - start_time).total_seconds() // 60), 0)
        except Exception:
            return None


def appdata_path(*parts: str) -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    return base.joinpath(*parts)
