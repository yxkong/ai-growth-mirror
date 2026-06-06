"""Beta adapter for Cursor local AI tracking data."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ...domain.session.model import SessionRef, SessionRecord
from ...domain.signals.taxonomy import InteractionKind
from ...domain.signals.tooling import compute_tier_counts, normalize_tool_name
from .base import (
    BaseSessionAdapter,
    EXEC_TOOL_NAMES,
    SKILL_READ_TOOL_NAMES,
    SUBAGENT_TOOL_NAMES,
    TEST_PATTERNS,
    WRITE_TOOL_NAMES,
    _common_prefix_path,
    content_revision_mtime,
    detect_authorship_path,
    detect_language,
    extract_skill_name_from_path,
    parse_ts,
)

_USER_QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL | re.IGNORECASE)
_PATH_INPUT_KEYS = ("path", "file_path", "target_file", "target_notebook", "notebook_path")



class CursorAdapter(BaseSessionAdapter):
    tool_name = "cursor"
    display_name = "Cursor"
    default_data_root = Path.home() / ".cursor"

    @property
    def _db_path(self) -> Path:
        return self.data_root / "ai-tracking" / "ai-code-tracking.db"

    def is_available(self) -> bool:
        if self._db_has_sessions():
            return True
        return self._has_agent_transcripts()

    def _db_has_sessions(self) -> bool:
        if not self._db_path.exists():
            return False
        try:
            with sqlite3.connect(self._db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM conversation_summaries"
                ).fetchone()[0]
        except sqlite3.Error:
            return False
        return count > 0

    @staticmethod
    def _is_root_transcript(jsonl_path: Path) -> bool:
        if "agent-transcripts" not in jsonl_path.parts:
            return False
        if "subagents" in jsonl_path.parts:
            return False
        return jsonl_path.parent.name == jsonl_path.stem

    def _has_agent_transcripts(self) -> bool:
        projects_dir = self.data_root / "projects"
        if not projects_dir.exists():
            return False
        for jsonl_path in projects_dir.rglob("*.jsonl"):
            if self._is_root_transcript(jsonl_path):
                return True
        return False

    @property
    def transcript_session_ids(self) -> set[str]:
        """IDs of sessions backed by JSONL transcripts (rich data)."""
        ids: set[str] = set()
        projects_dir = self.data_root / "projects"
        if not projects_dir.exists():
            return ids
        for jsonl_path in projects_dir.rglob("*.jsonl"):
            if self._is_root_transcript(jsonl_path):
                ids.add(jsonl_path.stem)
        return ids

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        seen: set[str] = set()

        if self._db_path.exists():
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT conversationId, updatedAt FROM conversation_summaries ORDER BY updatedAt ASC"
                ).fetchall()
            for row in rows:
                updated_at = row["updatedAt"]
                if not updated_at:
                    continue
                session_id = row["conversationId"]
                seen.add(session_id)
                yield SessionRef(
                    session_id=session_id,
                    tool_name=self.tool_name,
                    start_time=parse_ts(updated_at),
                    source_paths=[self._db_path],
                    source_mtime=content_revision_mtime(updated_at),
                )

        projects_dir = self.data_root / "projects"
        if not projects_dir.exists():
            return
        for jsonl_path in sorted(projects_dir.rglob("*.jsonl")):
            if not self._is_root_transcript(jsonl_path):
                continue
            session_id = jsonl_path.stem
            if session_id in seen:
                continue
            seen.add(session_id)
            start_time = self._read_transcript_start_time(jsonl_path)
            try:
                source_mtime = jsonl_path.stat().st_mtime
            except OSError:
                source_mtime = 0.0
            yield SessionRef(
                session_id=session_id,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=[jsonl_path],
                source_mtime=source_mtime,
            )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        if raw.source_paths and raw.source_paths[0].suffix.lower() == ".jsonl":
            return self._parse_transcript_jsonl(raw)
        return self._parse_db_session(raw)

    def _read_transcript_start_time(self, jsonl_path: Path) -> datetime:
        try:
            stat = jsonl_path.stat()
            ts = min(stat.st_ctime, stat.st_mtime)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except OSError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _extract_transcript_user_text(obj: dict) -> str:
        if obj.get("role") != "user":
            return ""
        content = obj.get("message", {}).get("content", [])
        if not isinstance(content, list):
            return ""
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                chunks.append(part.get("text", ""))
        return "\n".join(chunks).strip()

    @staticmethod
    def _first_prompt_from_user_text(text: str) -> str:
        if not text:
            return ""
        match = _USER_QUERY_RE.search(text)
        if match:
            return match.group(1).strip()[:500]
        return text[:500]

    @staticmethod
    def _path_from_tool_input(tool_input: object) -> str:
        if not isinstance(tool_input, dict):
            return ""
        for key in _PATH_INPUT_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _parse_transcript_jsonl(self, raw: SessionRef) -> SessionRecord:
        jsonl_path = raw.source_paths[0]
        tool_counts: Counter[str] = Counter()
        file_paths: set[str] = set()
        languages: Counter[str] = Counter()
        user_message_count = 0
        assistant_message_count = 0
        first_prompt = ""
        top_user_messages: list[str] = []
        uses_subagent = False
        uses_mcp = False
        uses_web_search = False
        uses_web_fetch = False
        subagent_invocation_count = 0
        skill_invocation_count = 0
        unique_skills: set[str] = set()
        unique_skills_from_attach: set[str] = set()
        skill_files_authored: set[str] = set()
        hook_config_modified = False
        mcp_server_authored = False
        chain_lengths: list[int] = []
        has_verification = False
        has_test_commands = False
        current_chain = 0
        pending_write = False
        shell_commands: list[str] = []
        advanced_features: set[str] = set()

        try:
            stat = jsonl_path.stat()
            end_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            end_ts = raw.start_time
        start_ts = raw.start_time

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                role = obj.get("role")
                if role == "user":
                    user_text = self._extract_transcript_user_text(obj)
                    if user_text:
                        user_message_count += 1
                        if not first_prompt:
                            first_prompt = self._first_prompt_from_user_text(user_text)
                        if len(top_user_messages) < 5:
                            top_user_messages.append(user_text[:300])
                        _has_skill_attach = (
                            "manually_attached_skills" in user_text.lower()
                            or "<agent_skill" in user_text
                            or "<available_skills" in user_text
                        )
                        if _has_skill_attach:
                            skill_invocation_count += 1
                            import re as _re
                            # Format A: XML <agent_skill fullPath="...">Description</agent_skill>
                            # Extract skill folder name from fullPath (e.g. "delivery-workflow")
                            for _fp in _re.findall(
                                r'<agent_skill[^>]+fullPath=["\']([^"\']+)["\']', user_text
                            ):
                                _folder = Path(_fp).parent.name
                                if _folder and _folder not in ("", ".", "skills", "skills-cursor"):
                                    unique_skills_from_attach.add(_folder)
                            # Format A fallback: description text inside <agent_skill>
                            if not unique_skills_from_attach:
                                for _desc in _re.findall(
                                    r'<agent_skill[^>]*>([^<]{5,100})</agent_skill>', user_text
                                ):
                                    _desc = _desc.strip()
                                    if _desc:
                                        unique_skills_from_attach.add(_desc[:60])
                            # Format B: bullet list "- skill-name (path)"
                            for _sk in _re.findall(r"[-*]\s*([^\n]+?)(?:\s*\(|$)", user_text):
                                _sk = _sk.strip()
                                if _sk and len(_sk) < 80:
                                    unique_skills_from_attach.add(_sk)
                            # Having skill library signals authorship intent
                            if unique_skills_from_attach:
                                skill_files_authored.add("__attached_skills__")
                                advanced_features.add("skill_invocation")
                        lower_user_text = user_text.lower()
                        if "plan mode is active" in lower_user_text:
                            advanced_features.add("plan_mode")
                        if "ask mode is active" in lower_user_text:
                            advanced_features.add("ask_mode")
                    if current_chain:
                        chain_lengths.append(current_chain)
                        current_chain = 0
                    pending_write = False
                    continue

                if role != "assistant":
                    continue

                assistant_message_count += 1
                content = obj.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") != "tool_use":
                        continue
                    tool_name = str(part.get("name", "")).strip()
                    if not tool_name:
                        continue
                    normalized = tool_name.lower()
                    tool_counts[normalized] += 1
                    current_chain += 1
                    tool_input = part.get("input", {})
                    path = self._path_from_tool_input(tool_input)
                    if path:
                        file_paths.add(path)
                        lang = detect_language(path)
                        if lang:
                            languages[lang] += 1
                        authorship = detect_authorship_path(path, self.asset_roots)
                        if authorship == "skill":
                            skill_files_authored.add(path)
                        elif authorship == "hook":
                            hook_config_modified = True
                        elif authorship == "mcp":
                            mcp_server_authored = True
                    if normalized in SUBAGENT_TOOL_NAMES or "task" in normalized:
                        uses_subagent = True
                        subagent_invocation_count += 1
                        advanced_features.add("subagent_dispatch")
                    if "mcp" in normalized:
                        uses_mcp = True
                        advanced_features.add("mcp_usage")
                    if "web_search" in normalized or normalized == "websearch":
                        uses_web_search = True
                    if "web_fetch" in normalized or "fetch" in normalized:
                        uses_web_fetch = True
                    if normalized in {"todowrite", "todo_write"}:
                        advanced_features.add("plan_mode")
                    # Detect skill usage: agent read a SKILL.md file from a skill folder.
                    # This is the canonical evidence of skill invocation in Cursor transcripts
                    # because agent rules/skills are not injected into user messages but the
                    # agent explicitly reads SKILL.md when it follows a skill.
                    if path and normalized in SKILL_READ_TOOL_NAMES:
                        skill_name = extract_skill_name_from_path(path)
                        if skill_name:
                            unique_skills.add(skill_name)
                            skill_invocation_count += 1
                            advanced_features.add("skill_invocation")
                    if normalized in WRITE_TOOL_NAMES or normalize_tool_name(normalized) == InteractionKind.WRITE:
                        pending_write = True
                    if normalized in EXEC_TOOL_NAMES or normalize_tool_name(normalized) == InteractionKind.BASH:
                        command = ""
                        if isinstance(tool_input, dict):
                            command = str(tool_input.get("command", ""))
                        if command:
                            shell_commands.append(command.lower())
                        if pending_write:
                            has_verification = True
                            pending_write = False
                        if any(p in command.lower() for p in TEST_PATTERNS):
                            has_test_commands = True

        if current_chain:
            chain_lengths.append(current_chain)

        project_path = _common_prefix_path(list(file_paths))
        if not project_path:
            project_path = _project_slug_to_hint(jsonl_path)

        duration_minutes = max(int((end_ts - start_ts).total_seconds() // 60), 0)
        session = SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            project_path=project_path,
            start_time=start_ts.isoformat(),
            end_time=end_ts.isoformat(),
            duration_minutes=duration_minutes,
            first_prompt=first_prompt,
            user_message_count=user_message_count,
            assistant_message_count=assistant_message_count,
            tool_counts=dict(tool_counts),
            tool_tier_counts=compute_tier_counts(dict(tool_counts)),
            files_modified=len(file_paths),
            languages=dict(languages),
            models_used=[],
            uses_subagent=uses_subagent,
            uses_mcp=uses_mcp,
            uses_web_search=uses_web_search,
            uses_web_fetch=uses_web_fetch,
            top_user_messages=top_user_messages,
            autonomous_chain_lengths=chain_lengths,
            has_verification_behavior=has_verification,
            has_test_commands=has_test_commands,
            skill_invocation_count=skill_invocation_count,
            unique_skills_used=sorted(unique_skills_from_attach | unique_skills),
            advanced_features=sorted(advanced_features),
            subagent_invocation_count=subagent_invocation_count,
            skill_files_authored=len(skill_files_authored),
            hook_config_modified=hook_config_modified,
            mcp_server_authored=mcp_server_authored,
            entrypoint="ide",
        )
        return session

    def _parse_db_session(self, raw: SessionRef) -> SessionRecord:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            summary = conn.execute(
                "SELECT * FROM conversation_summaries WHERE conversationId = ?",
                (raw.session_id,),
            ).fetchone()
            files = conn.execute(
                "SELECT gitPath, fileExtension, createdAt FROM tracked_file_content WHERE conversationId = ?",
                (raw.session_id,),
            ).fetchall()
            deleted = conn.execute(
                "SELECT gitPath, deletedAt FROM ai_deleted_files WHERE conversationId = ?",
                (raw.session_id,),
            ).fetchall()

        file_paths = [row["gitPath"] for row in files if row["gitPath"]]
        deleted_paths = [row["gitPath"] for row in deleted if row["gitPath"]]
        all_paths = file_paths + deleted_paths
        languages: Counter[str] = Counter()
        for row in files:
            ext = (row["fileExtension"] or "").strip().lower()
            if ext:
                languages[ext.lstrip(".")] += 1

        start_candidates = [row["createdAt"] for row in files if row["createdAt"]]
        start_ts = parse_ts(min(start_candidates)) if start_candidates else raw.start_time
        end_ts = parse_ts(summary["updatedAt"]) if summary and summary["updatedAt"] else start_ts
        first_prompt = ""
        if summary is not None:
            first_prompt = summary["title"] or summary["tldr"] or summary["overview"] or ""

        project_path = _common_prefix_path(file_paths)
        tool_counts = {"write": len(set(file_paths))} if file_paths else {}

        session = SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            project_path=project_path,
            start_time=start_ts.isoformat(),
            end_time=end_ts.isoformat(),
            duration_minutes=max(int((end_ts - start_ts).total_seconds() // 60), 0),
            first_prompt=first_prompt,
            user_message_count=0,  # unavailable from current Cursor DB schema
            assistant_message_count=0,  # unavailable from current Cursor DB schema
            tool_counts=tool_counts,
            files_modified=len(set(all_paths)),
            languages=dict(languages),
            models_used=[summary["model"]] if summary and summary["model"] else [],
            uses_subagent=False,
            uses_mcp=False,
            uses_web_search=False,
            uses_web_fetch=False,
            advanced_features=[],
        )
        return session





def _project_slug_to_hint(jsonl_path: Path) -> str:
    parts = jsonl_path.parts
    try:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    except ValueError:
        pass
    return ""
