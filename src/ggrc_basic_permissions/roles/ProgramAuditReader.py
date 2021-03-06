# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

scope = "AuditImplied"
description = """
  A user with the ProgramReader role for a private program will also have this
  role in the audit context for any audit created for that program.
  """
permissions = {
    "read": [
        "Snapshot",
        "Comment",
        "Assessment",
        "Issue",
        "Audit",
        "AuditObject",
        "ObjectPerson",
        "Relationship",
        "Document",
        "UserRole",
        "Context",
    ],
    "create": [],
    "view_object_page": [
        "__GGRC_ALL__"
    ],
    "update": [],
    "delete": []
}
