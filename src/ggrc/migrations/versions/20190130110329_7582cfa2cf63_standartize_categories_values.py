# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Standartize categories values

Create Date: 2019-01-30 11:03:29.157411
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = '7582cfa2cf63'
down_revision = 'f1130618060e'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()

  # getting names with backspace at the end, e.g. 'Backup Logs '
  rows_to_update = connection.execute(
      sa.text("""
          SELECT * FROM categories
          WHERE RIGHT(name,1)=' ';
      """)
  ).fetchall()
  for row in rows_to_update:
    name = row.name.strip()
    connection.execute(
        sa.text("""
            UPDATE categories
            SET name=:category_name
            WHERE id=:category_id;
        """),
        category_name=name,
        category_id=row.id
    )

  # getting rows with backspace after backslash,
  # e.g. 'Logical Access/ Access Control'
  rows_to_update = connection.execute(
      sa.text("""
          SELECT * FROM categories
          WHERE name LIKE '%/ %';
      """)
  ).fetchall()
  for row in rows_to_update:
    name = row.name.replace('/ ', '/')
    connection.execute(
        sa.text("""
            UPDATE categories
            SET name=:category_name
            WHERE id=:category_id;
        """),
        category_name=name,
        category_id=row.id
    )

  # getting rows with 'and' instead of '&',
  # e.g. 'Org and Admin/Governance'
  rows_to_update = connection.execute(
      sa.text("""
          SELECT * FROM categories
          WHERE name LIKE '%and%';
      """)
  ).fetchall()
  for row in rows_to_update:
    name = row.name.replace('and', '&')
    connection.execute(
        sa.text("""
            UPDATE categories
            SET name=:category_name
            WHERE id=:category_id;
        """),
        category_name=name,
        category_id=row.id
    )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
