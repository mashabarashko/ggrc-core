# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A module with configuration of the Reader role's permissions."""

# pylint: disable=invalid-name


from ggrc_basic_permissions.roles.Creator import owner_delete, \
    owner_update, owner_map


scope = "System"
description = """
  This role grants a user basic, read-only, access permission to a GGRC
  instance.
  """
permissions = {
    "read": [
        "AccessControlRole",
        "AccessControlList",
        "Audit",
        "BackgroundTask",
        "Snapshot",
        "Categorization",
        "Category",
        "ControlCategory",
        "ControlAssertion",
        "Control",
        "Comment",
        "Assessment",
        "AssessmentTemplate",
        "CustomAttributeDefinition",
        "CustomAttributeValue",
        "Issue",
        "ControlControl",
        "DataAsset",
        "AccessGroup",
        "Directive",
        "Contract",
        "Policy",
        "Regulation",
        "Standard",
        "Document",
        "Evidence",
        "Facility",
        "Market",
        "Objective",
        "ObjectControl",
        "ObjectObjective",
        "ObjectPerson",
        "Option",
        "OrgGroup",
        "Risk",
        "RiskAssessment",
        "Threat",
        "Vendor",
        "PopulationSample",
        "Product",
        "ProgramControl",
        "ProgramDirective",
        "Project",
        "Relationship",
        "Requirement",
        "SystemOrProcess",
        "System",
        "KeyReport",
        "Process",
        "Metric",
        "SystemControl",
        "ProductGroup",
        "SystemSystem",
        "Person",
        "Program",
        "Proposal",
        "TechnologyEnvironment",
        "Revision",
        "Role",
        "UserRole",
        "Context",
        "Workflow",
        "TaskGroup",
        "TaskGroupObject",
        "TaskGroupTask",
        "Cycle",
        "CycleTaskGroup",
        "CycleTaskGroupObjectTask",
        "CycleTaskEntry",
        "NotificationConfig",
        "PersonProfile",
    ],
    "create": [
        {
            "type": "Audit",
            "condition": "is_allowed_based_on",
            "terms": {
                "property_name": "program",
                "action": "update",
            }
        },
        "BackgroundTask",
        {
            "type": "Snapshot",
            "condition": "is_allowed_based_on",
            "terms": {
                "property_name": "parent",
                "action": "update",
            }
        },
        {
            "type": "Assessment",
            "condition": "is_auditor",
            "terms": {}
        },
        "AssessmentTemplate",
        "Workflow",
        {
            "type": "TaskGroup",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "TaskGroupTask",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "Cycle",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "CycleTaskEntry",
            "condition": "is_allowed_based_on",
            "terms": {
                "property_name": "cycle_task_group_object_task",
                "action": "update",
            }
        },
        {
            "type": "TaskGroupObject",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        "Categorization",
        "Category",
        "ControlCategory",
        "ControlAssertion",
        "Control",
        "Comment",
        "Issue",
        "DataAsset",
        "AccessGroup",
        "Directive",
        "Contract",
        "Policy",
        "Regulation",
        "Standard",
        "Evidence",
        "Document",
        "Facility",
        "Market",
        "Objective",
        "ObjectPerson",
        "Option",
        "OrgGroup",
        "Risk",
        "Threat",
        "Vendor",
        "PopulationSample",
        "Product",
        "Project",
        "Proposal",
        {
            "type": "Relationship",
            "terms": {
                "property_name": "source,destination",
                "action": "map"
            },
            "condition": "relationship",
        },
        "Requirement",
        "SystemOrProcess",
        "System",
        "KeyReport",
        "Process",
        "Metric",
        "TechnologyEnvironment",
        "Person",
        "ProductGroup",
        "Program",
        "Role",
        "Context",
        "BackgroundTask",
        "Review"
    ],
    "update": owner_update,
    "delete": owner_delete,
    "map": owner_map,
}
