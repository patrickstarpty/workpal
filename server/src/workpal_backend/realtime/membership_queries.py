"""Fresh membership checks on exact workspace/user pairs."""
from sqlalchemy import text
from ..infrastructure.go_uuid import parse_uuid


class MembershipQueries:
    def __init__(self, session):
        self.session = session

    def members(self, identities):
        pairs = []
        for workspace, user in identities:
            # Preserve Go validation order and original result-map keys.
            user_id = parse_uuid(user)
            workspace_id = parse_uuid(workspace)
            pairs.append((workspace_id, user_id))
        params = {}
        values = []
        for index, (workspace, user) in enumerate(pairs):
            values.append(f'(:w{index},:u{index})')
            params[f'w{index}'], params[f'u{index}'] = workspace, user
        if values:
            sql = ('WITH requested(workspace_id,user_id) AS (VALUES '+','.join(values)+') '
                   'SELECT m.workspace_id,m.user_id FROM members m JOIN requested r '
                   'ON m.workspace_id=r.workspace_id AND m.user_id=r.user_id')
        else:
            sql = 'SELECT workspace_id,user_id FROM members WHERE 0'
        current = {tuple(row) for row in self.session.execute(text(sql), params)}
        return {identity: True for identity, pair in zip(identities, pairs) if pair in current}
