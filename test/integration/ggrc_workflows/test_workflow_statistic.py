# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests endpoint for workflow statistics."""

from datetime import date

import ddt
from freezegun import freeze_time

from ggrc.models import all_models
from ggrc.utils import create_stub

from integration.ggrc.access_control import acl_helper
from integration.ggrc.models import factories
from integration.ggrc.services import TestCase
from integration.ggrc.query_helper import WithQueryApi
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc_workflows.generator import WorkflowsGenerator
from integration.ggrc.api_helper import Api


@ddt.ddt
class TestPersonResource(TestCase, WithQueryApi):
  """Tests endpoint for getting workflow statistics."""

  def setUp(self):
    super(TestPersonResource, self).setUp()
    self.client.get("/login")
    self.api = Api()
    self.generator = WorkflowsGenerator()
    self.object_generator = ObjectGenerator()

  def test_workflow_statistic(self):
    """Tests endpoint for getting workflow statistics."""
    # pylint: disable=too-many-locals
    user = all_models.Person.query.first()
    _, user1 = self.object_generator.generate_person(
        user_role="Administrator")
    user_id = user.id
    user1_id = user1.id
    role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.name == "Task Assignees",
        all_models.AccessControlRole.object_type == "TaskGroupTask",
    ).one()
    role_id = role.id
    workflow_template1 = {
        "title": "test wf 1",
        "is_verification_needed": True,
        "task_groups": [{
            "title": "task group 1",
            "contact": create_stub(user),
            "task_group_tasks": [{
                "title": "task 1",
                "description": "some task",
                "access_control_list": [
                    acl_helper.get_acl_json(role_id, user_id)],
                "start_date": date(2017, 5, 5),
                "end_date": date(2017, 8, 15),
            }, {
                "title": "task 2",
                "description": "some task",
                "access_control_list": [
                    acl_helper.get_acl_json(role_id, user_id)],
                "start_date": date(2017, 5, 5),
                "end_date": date(2017, 8, 16),
            }, {"title": "task 3",
                "description": "some task",
                "access_control_list": [
                    acl_helper.get_acl_json(role_id, user_id)],
                "start_date": date(2017, 5, 5),
                "end_date": date(2017, 8, 17),
                }
            ],
            "task_group_objects": []
        }, {
            "title": "task group 2",
            "contact": create_stub(user),
            "task_group_tasks": [{
                "title": "task 4",
                "description": "some task",
                "access_control_list": [
                    acl_helper.get_acl_json(role_id, user_id)],
                "start_date": date(2017, 5, 5),
                "end_date": date(2017, 8, 17),
            }],
            "task_group_objects": []
        }]
    }
    workflow_template2 = {
        "title": "test wf 2",
        "is_verification_needed": False,
        "task_groups": [{
            "title": "task group 1",
            "contact": create_stub(user),
            "task_group_tasks": [{
                "title": "task 5",
                "description": "some task",
                "access_control_list": [
                    acl_helper.get_acl_json(role_id, user_id)],
                "start_date": date(2017, 5, 5),
                "end_date": date(2017, 8, 17),
            }, {
                "title": "task 6",
                "description": "some task",
                "access_control_list": [
                    acl_helper.get_acl_json(role_id, user_id)],
                "start_date": date(2017, 5, 5),
                "end_date": date(2017, 8, 14)
            }, {
                "title": "task 7",
                "description": "some task",
                "access_control_list": [
                    acl_helper.get_acl_json(role_id, user_id)],
                "start_date": date(2017, 5, 5),
                "end_date": date(2017, 8, 17)
            }],
            "task_group_objects": []
        }]
    }
    with factories.single_commit():
      _, workflow1 = self.generator.generate_workflow(workflow_template1)
      _, workflow2 = self.generator.generate_workflow(workflow_template2)
      _, cycle1 = self.generator.generate_cycle(workflow1)
      _, cycle2 = self.generator.generate_cycle(workflow2)
      _, workflow1 = self.generator.activate_workflow(workflow1)
      _, workflow2 = self.generator.activate_workflow(workflow2)
      cycle1_id = cycle1.id
      cycle2_id = cycle2.id

    workflow1 = all_models.Workflow.query.get(workflow1.id)
    workflow1_id = workflow1.id
    workflow2_id = workflow2.id
    factories.AccessControlPersonFactory(
        ac_list=workflow1.acr_name_acl_map["Admin"],
        person=user1
    )
    with freeze_time("2017-8-16"):
      self.client.get("/login")
      workflow1 = all_models.Workflow.query.get(workflow1_id)
      wf1_title = workflow1.title
      workflow2 = all_models.Workflow.query.get(workflow2_id)
      wf2_title = workflow2.title
      user_email = all_models.Person.query.get(user_id).email
      user1_email = all_models.Person.query.get(user1_id).email

      cycle1 = all_models.Cycle.query.get(cycle1_id)
      cycle2 = all_models.Cycle.query.get(cycle2_id)
      task2 = cycle1.cycle_task_group_object_tasks[1]
      task3 = cycle1.cycle_task_group_object_tasks[2]
      task4 = cycle1.cycle_task_group_object_tasks[3]
      task5 = cycle2.cycle_task_group_object_tasks[0]
      task7 = cycle2.cycle_task_group_object_tasks[2]
      self.api.put(task2, {
          "status": "Finished"
      })
      self.api.put(task3, {
          "status": "Deprecated"
      })
      self.api.put(task4, {
          "status": "Verified"
      })
      self.api.put(task5, {
          "status": "Finished"
      })
      self.api.put(task7, {
          "status": "Deprecated"
      })
      workflow1_owners = [user_email, user1_email]
      response = self.client.get("/api/people/{}/my_workflows".format(user_id))
      expected_result = {'workflows': [{
          'workflow': {
              'id': workflow2.id,
              'title': wf2_title
          },
          'owners': [user_email],
          'task_stat': {
              'counts': {
                  'completed': 2,
                  'overdue': 1,
                  'total': 3
              },
              'due_in_date': '2017-08-14'
          }}, {
          'workflow': {
              'id': workflow1.id,
              'title': wf1_title
          },
          'owners': workflow1_owners,
          'task_stat': {
              'counts': {
                  'completed': 2,
                  'total': 4,
                  'overdue': 1,
              },
              'due_in_date': '2017-08-15'
          }},
      ]}
      self.assertEqual(response.json, expected_result)
