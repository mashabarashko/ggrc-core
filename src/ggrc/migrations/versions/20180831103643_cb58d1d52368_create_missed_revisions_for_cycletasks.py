# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Create missed revisions for CycleTasks unmapped objects

Create Date: 2018-08-31 10:36:43.151071
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op
from ggrc.migrations import utils


# revision identifiers, used by Alembic.
revision = 'cb58d1d52368'
down_revision = 'b46bdb31d869'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  program_sql = """
      SELECT p.id
      FROM programs AS p
      LEFT JOIN revisions AS r
          ON r.resource_type='Program' AND r.resource_id=p.id
      WHERE r.id IS NULL
  """
  programs = connection.execute(sa.text(program_sql)).fetchall()
  programs_ids = [o.id for o in programs]
  if programs_ids:
    utils.add_to_objects_without_revisions_bulk(connection, programs_ids,
                                                'Program')
  audit_sql = """
      SELECT a.id
      FROM audits AS a
      LEFT JOIN revisions AS r
          ON r.resource_type='Audit' AND r.resource_id=a.id
      WHERE r.id IS NULL
  """
  audits = connection.execute(sa.text(audit_sql)).fetchall()
  audits_ids = [o.id for o in audits]
  if audits_ids:
    utils.add_to_objects_without_revisions_bulk(connection, audits_ids,
                                                'Audit')


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
