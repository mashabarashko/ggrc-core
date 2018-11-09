# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Fix creation time for revisions for CycleTask Comments

Create Date: 2018-11-09 12:15:45.588583
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op


# revision identifiers, used by Alembic.
revision = '7152066dda1f'
down_revision = '9beabcd92f34'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  conn = op.get_bind()
  source_sql = """
    UPDATE revisions r
      JOIN
        comments c ON r.source_id = c.id AND r.source_type='Comment'
        AND r.destination_type='CycleTaskGroupObjectTask'
    SET
        r.created_at = c.created_at,
        r.updated_at = c.updated_at
    WHERE
        r.resource_type = 'Relationship';
    """
  conn.execute(source_sql)
  destination_sql = """
    UPDATE revisions r
      JOIN
        comments c ON r.destination_id = c.id AND r.destination_type='Comment'
        AND r.source_type='CycleTaskGroupObjectTask'
    SET
        r.created_at = c.created_at,
        r.updated_at = c.updated_at
    WHERE
        r.resource_type = 'Relationship';
    """
  conn.execute(destination_sql)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
