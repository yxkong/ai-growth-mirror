"""Filtering helpers for narrowing the analyzed session set."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .model import SessionRecord


def _normalized_texts(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(value.casefold() for value in values if value)


def _normalize_scope_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _iter_keyword_haystacks(session: SessionRecord) -> Iterator[str]:
    if session.first_prompt:
        yield session.first_prompt
    if session.project_path:
        yield session.project_path
    if session.git_origin_url:
        yield session.git_origin_url
    for message in session.top_user_messages or ():
        if message:
            yield message


def _contains_any(haystacks: Iterable[str], needles: Iterable[str]) -> bool:
    needle_pool = _normalized_texts(needles)
    if not needle_pool:
        return False
    for haystack in _normalized_texts(haystacks):
        if any(needle in haystack for needle in needle_pool):
            return True
    return False


def _path_matches(session_path: Path, filters: Iterable[Path]) -> bool:
    for filter_path in filters:
        normalized = _normalize_scope_path(filter_path)
        if session_path == normalized:
            return True
        try:
            session_path.relative_to(normalized)
            return True
        except ValueError:
            continue
    return False


@dataclass(frozen=True)
class SessionScope:
    """User-supplied scope for narrowing the analyzed session set."""

    repos: tuple[str, ...] = ()
    dirs: tuple[Path, ...] = ()
    keywords: tuple[str, ...] = ()

    @property
    def has_filters(self) -> bool:
        return any((self.repos, self.dirs, self.keywords))


def matches_session_scope(session: SessionRecord, scope: SessionScope) -> bool:
    if scope.repos:
        repo_haystacks = []
        if session.git_origin_url:
            repo_haystacks.append(session.git_origin_url)
        if session.project_path:
            repo_haystacks.append(Path(session.project_path).name)
        if not _contains_any(repo_haystacks, scope.repos):
            return False
    if scope.dirs:
        if not session.project_path:
            return False
        if not _path_matches(_normalize_scope_path(Path(session.project_path)), scope.dirs):
            return False
    if scope.keywords and not _contains_any(_iter_keyword_haystacks(session), scope.keywords):
        return False
    return True


def apply_session_scope(sessions: list[SessionRecord], scope: SessionScope) -> list[SessionRecord]:
    if not scope.has_filters:
        return list(sessions)
    return [session for session in sessions if matches_session_scope(session, scope)]
