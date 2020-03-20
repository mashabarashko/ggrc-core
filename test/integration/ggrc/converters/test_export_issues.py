# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

# pylint: disable=maybe-no-member, invalid-name

"""Test Issue export."""
import datetime

import ddt

from integration.ggrc.models import factories
from integration.ggrc import TestCase
from integration.ggrc import api_helper


@ddt.ddt
class TestExportIssues(TestCase):
  """Basic Issue export tests."""

  def setUp(self):
    super(TestExportIssues, self).setUp()
    self.client.get("/login")

  def test_issue_due_date_export(self):
    """Test issue due date export."""
    factories.IssueFactory(due_date=datetime.date(2018, 6, 14))
    data = [{
        "object_name": "Issue",
        "filters": {
            "expression": {}
        },
        "fields": "all"
    }]
    response = self.export_csv(data)
    self.assertIn("06/14/2018", response.data)


@ddt.ddt
class TestExportIssuesExternal(TestCase):
  """Basic Issue export tests."""

  def setUp(self):
    super(TestExportIssuesExternal, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  @ddt.data('AccessGroup',
            'AccountBalance',
            'Audit',
            'Assessment',
            'Contract',
            'Control',
            'CycleTaskGroupObjectTask',
            'DataAsset',
            'Facility',
            'Issue',
            'KeyReport',
            'Market',
            'Metric',
            'Objective',
            'OrgGroup',
            'Policy',
            'Process',
            'Product',
            'ProductGroup',
            'Program',
            'Project',
            'Regulation',
            'Requirement',
            'Risk',
            'Standard',
            'System',
            'TechnologyEnvironment',
            'Threat',
            'Vendor')
  def test_export_issue_mapping_external(self, map_name):
    """Test issue export mapping object"""
    with factories.single_commit():
      issue = factories.IssueFactory()
      obj = factories.get_model_factory(map_name)()
      factories.RelationshipFactory(source=issue, destination=obj)
    obj_slug = obj.slug
    data = [{
        "object_name": "Issue",
        "fields": "all",

        "filters": {"expression": {}},
    }]
    response = self.export_csv(data)
    self.assert200(response)
    self.assertTrue(obj_slug in response.data)
