"""Owner-approved, time-aware knowledge for the support assistant.

Ported verbatim from the live sales bot (`bakbot/support_knowledge.py`) — it
already had no dependency on that bot, so only the shared store accessor at
the bottom of this file is new.

It owns a tiny private JSON store, record validation, lifecycle transitions
and relevance selection. Customer-facing code may read only records that are
both approved and currently in effect.
"""
from __future__ import annotations

import copy
import json
import os
import re
import secrets
import threading
import time
import unicodedata
from typing import Callable

SCHEMA_VERSION = 1
KINDS = {'incident', 'maintenance', 'product', 'policy', 'faq', 'style', 'reaction'}
STATUSES = {'draft', 'scheduled', 'active', 'resolved', 'expired', 'rejected'}
TEMPORARY_KINDS = {'incident', 'maintenance'}
ACTIVE_BASE = {'active', 'scheduled'}
MAX_TITLE = 120
MAX_BODY = 1200
MAX_SCOPE_VALUES = 24
_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
_TOKEN_RX = re.compile(r'[\w\u0600-\u06ff]{2,}', re.UNICODE)
_STOP = {
    'این', 'اون', 'آن', 'برای', 'همین', 'یک', 'من', 'ما', 'شما', 'که', 'از',
    'به', 'در', 'با', 'رو', 'را', 'و', 'یا', 'چی', 'چیه', 'چطور', 'چگونه',
}


def _norm(value) -> str:
    text = unicodedata.normalize('NFC', str(value or '')).translate(_FA_DIGITS)
    text = text.replace('ي', 'ی').replace('ك', 'ک').casefold()
    return re.sub(r'\s+', ' ', text).strip()


def _tokens(value) -> set[str]:
    return {t for t in _TOKEN_RX.findall(_norm(value)) if t not in _STOP}


def _int_ts(value, field: str, *, optional: bool = True) -> int | None:
    if value in (None, '') and optional:
        return None
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field} must be a Unix timestamp') from exc
    if out < 0:
        raise ValueError(f'{field} must be non-negative')
    return out


def _scope(scope) -> dict[str, list[str]]:
    if scope in (None, ''):
        return {}
    if not isinstance(scope, dict):
        raise ValueError('scope must be an object')
    out = {}
    for raw_key, raw_values in scope.items():
        key = _norm(raw_key)
        if not key or len(key) > 40:
            raise ValueError('invalid scope key')
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        clean = []
        for value in values:
            value = str(value or '').strip()
            if value and value not in clean:
                clean.append(value[:100])
        if clean:
            out[key] = clean[:MAX_SCOPE_VALUES]
    return out


def validate_record(record: dict, *, approving: bool = False) -> dict:
    """Return a normalized copy or raise ``ValueError``."""
    if not isinstance(record, dict):
        raise ValueError('record must be an object')
    out = copy.deepcopy(record)
    if not re.fullmatch(r'[a-f0-9]{8,32}', str(out.get('id') or '')):
        raise ValueError('invalid record id')
    kind = _norm(out.get('kind'))
    if kind not in KINDS:
        raise ValueError('invalid record kind')
    out['kind'] = kind
    status = _norm(out.get('status') or 'draft')
    if status not in STATUSES:
        raise ValueError('invalid record status')
    out['status'] = status
    title = str(out.get('title') or '').strip()
    body = str(out.get('body') or '').strip()
    if len(title) > MAX_TITLE or len(body) > MAX_BODY:
        raise ValueError('record text is too long')
    if approving and (not title or not body):
        raise ValueError('approved records require title and body')
    out['title'], out['body'] = title, body
    out['scope'] = _scope(out.get('scope'))
    out['start_ts'] = _int_ts(out.get('start_ts'), 'start_ts')
    out['expires_ts'] = _int_ts(out.get('expires_ts'), 'expires_ts')
    if out['start_ts'] is not None and out['expires_ts'] is not None:
        if out['expires_ts'] <= out['start_ts']:
            raise ValueError('expiry must be after start')
    if approving and kind in TEMPORARY_KINDS and out['expires_ts'] is None:
        raise ValueError('temporary records require expiry')
    try:
        out['priority'] = int(out.get('priority', 50))
    except (TypeError, ValueError) as exc:
        raise ValueError('priority must be an integer') from exc
    if not 0 <= out['priority'] <= 100:
        raise ValueError('priority must be from 0 to 100')
    out['version'] = max(1, int(out.get('version') or 1))
    out['origin'] = str(out.get('origin') or 'admin')[:40]
    out['creator'] = str(out.get('creator') or '')[:40]
    out['created_ts'] = _int_ts(out.get('created_ts'), 'created_ts', optional=False)
    out['updated_ts'] = _int_ts(out.get('updated_ts'), 'updated_ts', optional=False)
    out['approved_ts'] = _int_ts(out.get('approved_ts'), 'approved_ts')
    out['approved_by'] = str(out.get('approved_by') or '')[:40]
    out['resolved_ts'] = _int_ts(out.get('resolved_ts'), 'resolved_ts')
    out['resolved_by'] = str(out.get('resolved_by') or '')[:40]
    meta = out.get('meta') or {}
    out['meta'] = copy.deepcopy(meta) if isinstance(meta, dict) else {}
    return out


def effective_status(record: dict, now: int | None = None) -> str:
    now = int(time.time() if now is None else now)
    status = record.get('status') or 'draft'
    if status not in ACTIVE_BASE:
        return status
    expires = record.get('expires_ts')
    if expires is not None and now >= int(expires):
        return 'expired'
    start = record.get('start_ts')
    if start is not None and now < int(start):
        return 'scheduled'
    return 'active'


def find_conflicts(records: list[dict]) -> list[tuple[str, str]]:
    """Find equal-priority active facts with the same title/scope but different bodies."""
    conflicts = []
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if left.get('priority') != right.get('priority'):
                continue
            same_title = _norm(left.get('title')) == _norm(right.get('title'))
            left_scope = {v for values in (left.get('scope') or {}).values()
                          for v in map(_norm, values)}
            right_scope = {v for values in (right.get('scope') or {}).values()
                           for v in map(_norm, values)}
            same_scope = bool(left_scope and right_scope and left_scope & right_scope)
            if (same_title or same_scope) and _norm(left.get('body')) != _norm(right.get('body')):
                conflicts.append((left['id'], right['id']))
    return conflicts


class KnowledgeStore:
    def __init__(self, path: str, audit: Callable[..., None] | None = None,
                 now_fn: Callable[[], float] = time.time):
        self.path = path
        self.audit = audit
        self.now_fn = now_fn
        self._lock = threading.RLock()
        self._data = {'schema': SCHEMA_VERSION, 'records': []}
        self._has_valid_snapshot = False
        self._write_blocked = False
        self._error = ''
        self.reload()

    @property
    def error(self) -> str:
        return self._error

    @property
    def write_blocked(self) -> bool:
        return self._write_blocked

    def _emit(self, event: str, **fields):
        if self.audit:
            try:
                self.audit(event, **fields)
            except Exception:
                pass

    def reload(self) -> bool:
        with self._lock:
            if not os.path.exists(self.path):
                self._data = {'schema': SCHEMA_VERSION, 'records': []}
                self._has_valid_snapshot = True
                self._write_blocked = False
                self._error = ''
                return True
            try:
                with open(self.path, encoding='utf-8') as handle:
                    raw = json.load(handle)
                if not isinstance(raw, dict) or raw.get('schema') != SCHEMA_VERSION:
                    raise ValueError('unsupported knowledge schema')
                records = [validate_record(
                    r, approving=r.get('status') in {'scheduled', 'active', 'resolved', 'expired'})
                           for r in (raw.get('records') or [])]
                if len({r['id'] for r in records}) != len(records):
                    raise ValueError('duplicate record id')
                self._data = {'schema': SCHEMA_VERSION, 'records': records}
                self._has_valid_snapshot = True
                self._write_blocked = False
                self._error = ''
                return True
            except Exception as exc:
                self._error = f'{type(exc).__name__}: {exc}'[:240]
                self._write_blocked = True
                self._emit('support_knowledge_load_failed', error=type(exc).__name__)
                return False

    def _persist(self):
        if self._write_blocked:
            raise RuntimeError('knowledge writes blocked: reload/repair required')
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        payload = json.dumps(self._data, ensure_ascii=False, indent=1)
        tmp = f'{self.path}.tmp.{os.getpid()}.{threading.get_ident()}'
        try:
            with open(tmp, 'w', encoding='utf-8') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _commit_records(self, records: list[dict]):
        old = self._data
        self._data = {'schema': SCHEMA_VERSION, 'records': records}
        try:
            self._persist()
        except Exception:
            self._data = old
            raise

    def _find(self, record_id: str) -> tuple[int, dict]:
        for index, record in enumerate(self._data['records']):
            if record['id'] == record_id:
                return index, record
        raise KeyError(record_id)

    def create_draft(self, *, kind: str, title: str = '', body: str = '',
                     scope=None, start_ts=None, expires_ts=None, priority=50,
                     creator='', origin='admin', meta=None,
                     idempotency_key: str = '') -> dict:
        with self._lock:
            if idempotency_key:
                for record in self._data['records']:
                    if (record.get('meta') or {}).get('idempotency_key') == idempotency_key:
                        return copy.deepcopy(record)
            now = int(self.now_fn())
            meta = copy.deepcopy(meta) if isinstance(meta, dict) else {}
            if idempotency_key:
                meta['idempotency_key'] = str(idempotency_key)[:100]
            record = validate_record({
                'id': secrets.token_hex(6), 'kind': kind, 'status': 'draft',
                'title': title, 'body': body, 'scope': scope or {},
                'start_ts': start_ts, 'expires_ts': expires_ts,
                'priority': priority, 'version': 1, 'origin': origin,
                'creator': creator, 'created_ts': now, 'updated_ts': now,
                'approved_ts': None, 'approved_by': '', 'resolved_ts': None,
                'resolved_by': '', 'meta': meta,
            })
            records = list(self._data['records'])
            records.append(record)
            self._commit_records(records)
            self._emit('support_knowledge_draft_created', record_id=record['id'],
                       kind=record['kind'], actor=creator)
            return copy.deepcopy(record)

    def update_draft(self, record_id: str, *, actor='', expected_version=None,
                     **changes) -> dict:
        allowed = {'kind', 'title', 'body', 'scope', 'start_ts', 'expires_ts',
                   'priority', 'meta'}
        if set(changes) - allowed:
            raise ValueError('unsupported draft field')
        with self._lock:
            index, old = self._find(record_id)
            if old['status'] != 'draft':
                raise ValueError('only drafts can be edited')
            if expected_version is not None and int(expected_version) != old['version']:
                raise ValueError('stale draft version')
            updated = copy.deepcopy(old)
            updated.update(changes)
            updated['version'] += 1
            updated['updated_ts'] = int(self.now_fn())
            updated = validate_record(updated)
            records = list(self._data['records'])
            records[index] = updated
            self._commit_records(records)
            self._emit('support_knowledge_draft_updated', record_id=record_id,
                       actor=actor)
            return copy.deepcopy(updated)

    def approve(self, record_id: str, *, actor='', expected_version=None) -> dict:
        with self._lock:
            index, old = self._find(record_id)
            if old['status'] != 'draft':
                raise ValueError('only drafts can be approved')
            if expected_version is not None and int(expected_version) != old['version']:
                raise ValueError('stale draft version')
            now = int(self.now_fn())
            updated = copy.deepcopy(old)
            updated['status'] = 'scheduled' if updated.get('start_ts') and updated['start_ts'] > now else 'active'
            updated['approved_ts'] = now
            updated['approved_by'] = str(actor)[:40]
            updated['updated_ts'] = now
            updated['version'] += 1
            updated = validate_record(updated, approving=True)
            records = list(self._data['records'])
            records[index] = updated
            self._commit_records(records)
            self._emit('support_knowledge_approved', record_id=record_id,
                       kind=updated['kind'], actor=actor)
            return copy.deepcopy(updated)

    def reject(self, record_id: str, *, actor='') -> dict:
        return self._finish(record_id, 'rejected', actor)

    def resolve(self, record_id: str, *, actor='') -> dict:
        return self._finish(record_id, 'resolved', actor)

    def _finish(self, record_id: str, status: str, actor: str) -> dict:
        with self._lock:
            index, old = self._find(record_id)
            if status == 'rejected' and old['status'] != 'draft':
                raise ValueError('only drafts can be rejected')
            if status == 'resolved' and effective_status(old, int(self.now_fn())) not in ACTIVE_BASE:
                raise ValueError('only active/scheduled records can be resolved')
            updated = copy.deepcopy(old)
            now = int(self.now_fn())
            updated['status'] = status
            updated['resolved_ts'] = now
            updated['resolved_by'] = str(actor)[:40]
            updated['updated_ts'] = now
            updated['version'] += 1
            updated = validate_record(updated, approving=status != 'rejected')
            records = list(self._data['records'])
            records[index] = updated
            self._commit_records(records)
            self._emit(f'support_knowledge_{status}', record_id=record_id, actor=actor)
            return copy.deepcopy(updated)

    def delete(self, record_id: str, *, actor='') -> bool:
        with self._lock:
            index, record = self._find(record_id)
            records = list(self._data['records'])
            del records[index]
            self._commit_records(records)
            self._emit('support_knowledge_deleted', record_id=record_id,
                       kind=record['kind'], actor=actor)
            return True

    def get(self, record_id: str) -> dict | None:
        with self._lock:
            try:
                _, record = self._find(record_id)
            except KeyError:
                return None
            out = copy.deepcopy(record)
            out['effective_status'] = effective_status(out, int(self.now_fn()))
            return out

    def list_records(self, status: str | None = None, kind: str | None = None) -> list[dict]:
        now = int(self.now_fn())
        with self._lock:
            out = []
            for record in self._data['records']:
                item = copy.deepcopy(record)
                item['effective_status'] = effective_status(item, now)
                if status and item['effective_status'] != status:
                    continue
                if kind and item['kind'] != kind:
                    continue
                out.append(item)
            return sorted(out, key=lambda r: (-r['priority'], -r['updated_ts'], r['id']))

    def active_for(self, question: str, *, kinds=None, limit: int = 6) -> list[dict]:
        now = int(self.now_fn())
        q_norm, q_tokens = _norm(question), _tokens(question)
        allowed = set(kinds) if kinds else KINDS - {'style', 'reaction'}
        scored = []
        with self._lock:
            for record in self._data['records']:
                if record['kind'] not in allowed or effective_status(record, now) != 'active':
                    continue
                hay = ' '.join([record['title'], record['body']] + [
                    str(v) for values in record.get('scope', {}).values() for v in values])
                tokens = _tokens(hay)
                overlap = len(q_tokens & tokens)
                scope_hits = sum(1 for values in record.get('scope', {}).values()
                                 for value in values if _norm(value) and _norm(value) in q_norm)
                phrase = 2 if _norm(record['title']) and _norm(record['title']) in q_norm else 0
                score = overlap + 3 * scope_hits + phrase
                if score > 0:
                    scored.append((score, record['priority'], record['updated_ts'], record))
        scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]['id']))
        return [copy.deepcopy(item[3]) for item in scored[:max(1, min(limit, 20))]]

    def style_rules(self) -> list[dict]:
        return [r for r in self.list_records(status='active', kind='style')]

    def reaction_rules(self, question: str, limit: int = 4) -> list[dict]:
        return self.active_for(question, kinds={'reaction'}, limit=limit)


# ── shared instance ─────────────────────────────────────────────────────────
_STORE: KnowledgeStore | None = None
_STORE_LOCK = threading.Lock()


def _log_audit(event: str, **fields) -> None:
    """Store-level audit trail.

    Deliberately the log, not `services/audit.record_audit`: that one is async
    and needs a DB session, while the store is sync and holds its own lock.
    Admin routes that change knowledge record the real audit row themselves.
    """
    from app.utils.logger import bot_logger
    bot_logger.info(f'[SUPPORT-KB] {event} ' + ' '.join(f'{k}={v}' for k, v in fields.items()))


def store() -> KnowledgeStore:
    """The app-wide knowledge store (`src/app/data/support_knowledge.json`)."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            from app.core.paths import data_path
            _STORE = KnowledgeStore(data_path('support_knowledge.json'), audit=_log_audit)
        return _STORE
