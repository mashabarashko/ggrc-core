# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Introduce map permission

Create Date: 2019-02-19 09:28:25.396290
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op


# revision identifiers, used by Alembic.
revision = '623f05ce74bd'
down_revision = '3f80820cbf08'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.execute("""
    ALTER TABLE access_control_roles
    ADD map tinyint(1) NOT NULL DEFAULT '1'
    AFTER `delete`;
  """)

  op.execute("""
    UPDATE access_control_roles
    SET map=`update`;
  """)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
