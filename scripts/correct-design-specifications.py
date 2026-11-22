"""Separate existing functional specifications from new technical design documents."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sqlite3
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.workspaces.models import workspaces, members
from workpal_backend.workspace_content import repository as repo

ROOT = Path(__file__).resolve().parents[1]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
TECHNICAL = {
2: ('Ticket relationship navigation', [
('Data and authorization', 'Store directed links as workspace_id, source_issue_id, target_issue_id and relation_type. Enforce uniqueness for that tuple. Validate both issue IDs within the authenticated workspace and reject self-links.'),
('Interface contract', 'Proposed relation create/delete endpoints must resolve workspace membership before reading either ticket. Return the stored relation on success; return a conflict for duplicate links. This is a proposed contract, not an assertion that the endpoint exists.'),
('Client state', 'Keep query, selected target, pending operation and error separately. Cancel stale searches using a request generation counter. Preserve selection on failed writes; update the visible link only after acknowledgement.'),
('Failure and verification', 'Test concurrent duplicate creates, revoked membership and deleted targets. Verify keyboard focus against FDS FR-01–FR-04; persistence and isolation tests must inspect saved rows.')]),
8: ('Upload recovery interactions', [
('State model', 'Use idle, uploading, interrupted, authorization_required, file_required, cancelled and completed states. Track an upload ID, generation counter, confirmed bytes and continuation capability independently.'),
('Boundary contract', 'The UI consumes progress and capability information from an upload adapter. An unknown continuation capability permits restart only. A successful adapter response must include a durable attachment ID before completed is entered.'),
('Cancellation and identity', 'Cancel increments the generation counter and aborts the active request. Ignore callbacks from earlier generations. File reselection must compare the expected size and identity before reusing an upload ID.'),
('Failure and verification', 'Check late completion after Cancel, auth expiry, unavailable file bytes and duplicate Retry clicks. Test accessibility behavior against the corresponding FDS requirements; no passing result is implied by this design.')]),
14: ('Empty inbox guidance', [
('Query model', 'Key requests by workspace and normalized filter values. Store request status independently from the returned items; a failed or pending response cannot produce a successful empty state.'),
('State derivation', 'Derive empty_inbox only from a successful unfiltered zero-item response, and no_matches from a successful filtered zero-item response. Retain prior data during background revalidation.'),
('Filter reset', 'Clear only inbox filter state and issue a request for the same workspace. Use request identity to prevent an older filtered response replacing the reset result. Announce results after the matching request completes.'),
('Verification', 'Cover zero results, errors, filter reset races and workspace switching. Check the FDS empty-state copy, focus destination and live-region behavior separately from request correctness.')]),
20: ('Flexible workflow entry', [
('Persistence model', 'Store stage independently from status in ticket metadata. Preserve selected input document IDs and versions, rather than copying a mutable document title as the only reference.'),
('Mutation boundary', 'An authenticated stage edit validates the allowed stage value and records a stage_changed event in the same transaction. It must not also set status to done or synthesize a run.'),
('Input resolution', 'Resolve input IDs within the workspace and retain exact revisions. A missing or inaccessible input produces an explicit validation error. Switching stage must preserve the draft until the edit succeeds.'),
('Verification', 'Check independent stage/status edits, persistence after reload, inaccessible inputs and duplicate submissions. Implementation and review acceptance remain separate from this specification.')]),
7: ('Upload interruption recovery', [
('Coordinator model', 'Maintain a single active attempt per upload ID. Each attempt owns a generation token; callback processing requires both matching upload ID and generation. Separate transport progress from durable server acknowledgement.'),
('Persistence contract', 'Proposed finalization uses an idempotency key scoped to workspace, ticket and upload ID. Validate target access again at finalization and return the same attachment ID for a repeated successful finalize.'),
('Recovery limits', 'Persist confirmed server offset only when continuation is supported. Otherwise restart with explicitly selected bytes. On cancellation invalidate queued retries; do not convert an interrupted request into a completed attachment.'),
('Verification', 'Test repeated finalization, concurrent retries, stale callbacks, authorization changes and workspace changes. Map interaction acceptance to FDS-SMART-7 and the detailed upload behavior in FDS-SMART-8.')]),
15: ('Accessible ticket titles', [
('Editor state', 'Keep persistedTitle, draftTitle, editing, saving, error and baseRevision separately. Entering edit copies persistedTitle into draftTitle. Cancel discards the draft; a failed save keeps it intact.'),
('API and persistence', 'Submit title changes to the existing authenticated issue PATCH boundary. Server validation trims for emptiness and enforces the title length limit before persisting. Reconcile the returned title only after a successful response.'),
('Concurrent updates', 'Proposed optimistic concurrency sends the base revision with the update and rejects stale revisions with a conflict. Until that contract is implemented, do not claim concurrent overwrites are prevented; show a reconciliation prompt when a changed remote title is observed.'),
('Focus and verification', 'Keep a stable edit-control ref for focus restoration. Associate the input with a visible label and validation error, and announce save state. Verify Save, Cancel, rejected values, failed writes and remote updates against FDS FR-01–FR-05.')]),
}


def document(template, number, technical=False):
    with ZipFile(BytesIO(template)) as source:
        parts = {name: source.read(name) for name in source.namelist()}
    if not technical:
        for name, value in parts.items():
            if name.endswith('.xml'):
                parts[name] = value.replace(b'TDS-SMART-', b'FDS-SMART-').replace(
                    b'FUNCTIONAL DESIGN', b'FUNCTIONAL DESIGN SPECIFICATION')
    else:
        xml = ET.fromstring(parts['word/document.xml'])
        xml.attrib.pop('{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable', None)
        body = xml.find('{' + W + '}body')
        section = deepcopy(body.find('{' + W + '}sectPr'))
        body.clear()
        def paragraph(text, style=None):
            p = ET.SubElement(body, '{' + W + '}p')
            if style:
                prop = ET.SubElement(p, '{' + W + '}pPr')
                ET.SubElement(prop, '{' + W + '}pStyle', {'{' + W + '}val': style})
            r = ET.SubElement(p, '{' + W + '}r')
            ET.SubElement(r, '{' + W + '}t').text = text
        title, sections = TECHNICAL[number]
        paragraph(title, 'Title')
        paragraph(f'TDS-SMART-{number} | Technical Design Specification | Version 1.0')
        paragraph('Functional baseline', 'Heading1')
        paragraph(f'Input: FDS-SMART-{number} v1.0. The FDS defines user behavior and acceptance; this TDS specifies the proposed implementation. It is not an execution or approval record.')
        for heading, content in sections:
            paragraph(heading, 'Heading1')
            paragraph(content)
        paragraph('Delivery boundary', 'Heading1')
        paragraph('Implementation must provide a scoped change, review findings and actual test results. Proposed interfaces and concurrency guarantees require implementation and verification before acceptance.')
        body.append(section)
        parts['word/document.xml'] = ET.tostring(xml, encoding='utf-8', xml_declaration=True)
        for name in parts:
            if name.startswith('word/header') and name.endswith('.xml'):
                parts[name] = parts[name].replace(b'FUNCTIONAL DESIGN', b'TECHNICAL DESIGN SPECIFICATION')
        parts['docProps/core.xml'] = parts['docProps/core.xml'].replace(b'functional design', b'technical design')
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as target:
        for name, value in parts.items():
            if name.endswith('.xml'):
                ET.fromstring(value)
            target.writestr(name, value)
    return output.getvalue()


def main():
    db = Database(Settings())
    try:
        backup = db.engine.url.database + '.before-fds-tds-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        with sqlite3.connect(db.engine.url.database) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        with db.transaction() as session:
            wid = session.scalar(select(workspaces.c.id).where(workspaces.c.slug == 'workpal-team'))
            owner = session.scalar(select(members.c.user_id).where(members.c.workspace_id == wid, members.c.role == 'owner'))
            # Correct references in the original authored notes without making them execution evidence.
            for comment in repo.list_records(session, wid, 'comments'):
                text = comment.get('content', '')
                if 'TDS-SMART-' in text and not comment.get('design_kind'):
                    comment = {**comment, 'content': text.replace('TDS-SMART-', 'FDS-SMART-').replace('TDS v1.0', 'FDS v1.0')}
                    repo.put_record(session, wid, 'comments', comment)
            for number in TECHNICAL:
                aid = f'smart-tds-v1-{number}'
                original = repo.get_record(session, wid, 'attachments', aid)
                if original.get('design_kind') == 'fds':
                    continue
                raw = repo.get_record(session, wid, 'attachment_contents', aid)
                template = base64.b64decode(raw['data'])
                repo.put_record(session, wid, 'design_original_contents', raw)
                for kind in ('fds', 'tds'):
                    data = document(template, number, technical=kind == 'tds')
                    filename = f'{kind.upper()}-SMART-{number}.docx'
                    path = ROOT / 'apps/web/public/delivery' / kind / filename
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    now = datetime.now(timezone.utc).isoformat()
                    identity = aid if kind == 'fds' else f'smart-technical-v1-{number}'
                    cid = original['comment_id'] if kind == 'fds' else str(uuid4())
                    previous = repo.get_record(session, wid, 'comments', cid) if kind == 'fds' else None
                    attachment = {**original, 'id': identity, 'comment_id': cid, 'filename': filename,
                        'design_kind': kind, 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data),
                        'url': '/api/attachments/' + identity + '/content',
                        'download_url': '/api/attachments/' + identity + '/download',
                        'attachment_download_url': '/api/attachments/' + identity + '/download',
                        'created_at': original['created_at'] if kind == 'fds' else now}
                    label = 'Functional Design Specification' if kind == 'fds' else 'Technical Design Specification'
                    content = f'## {label} · {kind.upper()} v1.0\n\n{kind.upper()}-SMART-{number}'
                    content += (' defines user behavior, interaction states and acceptance requirements.' if kind == 'fds'
                                else f' describes implementation design based on FDS-SMART-{number} v1.0: state, interfaces, persistence and failure handling.')
                    comment = {'id': cid, 'workspace_id': wid, 'issue_id': original['issue_id'],
                        'type': 'comment', 'author_type': 'member', 'author_id': owner,
                        'created_at': previous['created_at'] if previous else now, 'updated_at': now,
                        'content': content, 'attachments': [attachment], 'design_kind': kind}
                    repo.put_record(session, wid, 'attachments', attachment)
                    repo.put_record(session, wid, 'attachment_contents', {
                        'id': identity, 'encoding': 'base64', 'data': base64.b64encode(data).decode()})
                    repo.put_record(session, wid, 'comments', comment)
        print('Separated six FDS/TDS pairs. Backup:', backup)
    finally:
        db.close()


if __name__ == '__main__':
    main()
