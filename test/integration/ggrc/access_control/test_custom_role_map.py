# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test simple map actions for custom roles."""

import ddt

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
  import factories as rbac_factories


@ddt.ddt
class TestCustomRoleMap(TestCase):
  """Test class with cases for custom roles creation
  with and without map permission for various objects
  and creation relationships between these objects."""

  def setUp(self):
    super(TestCustomRoleMap, self).setUp()
    self.api = Api()
    self.client.get("/login")

  @ddt.data(
      ({"update": True, "map": False,},
       {"update": False, "map": True,}, 403,),
      ({"update": False, "map": True,},
       {"update": True, "map": False,}, 403,),
      ({"update": True, "map": False,},
       {"update": True, "map": False,}, 403,),
      ({"update": False, "map": True,},
       {"update": False, "map": True,}, 201,),
  )
  @ddt.unpack
  def test_custom_role_map(self, program_permissions,
                           objective_permissions, result_status):
    """Program update {}, map {}; objective update {}, map {}."""
    program_role_name = "Custom Program Role"
    objective_role_name = "Custom Objective Role"
    factories.AccessControlRoleFactory(
        name=program_role_name,
        object_type="Program",
        update=program_permissions['update'],
        map=program_permissions['map']
    )
    factories.AccessControlRoleFactory(
        name=objective_role_name,
        object_type="Objective",
        update=objective_permissions['update'],
        map=objective_permissions['map']
    )
    with factories.single_commit():
      program = factories.ProgramFactory()
      objective = factories.ObjectiveFactory()

      # create person with authorizations
      person = factories.PersonFactory()
      creator_role = all_models.Role.query.filter(
        all_models.Role.name == 'Creator'
      ).one()
      rbac_factories.UserRoleFactory(role=creator_role, person=person)

      factories.AccessControlPersonFactory(
          ac_list=program.acr_name_acl_map[program_role_name],
          person=person,
      )
      factories.AccessControlPersonFactory(
          ac_list=objective.acr_name_acl_map[objective_role_name],
          person=person,
      )

    program = all_models.Program.query.first()
    objective = all_models.Objective.query.first()
    self.api.set_user(person)
    self.client.get("/login")
    response = self.api.post(all_models.Relationship, {
      "relationship": {
        "source": {"id": program.id, "type": program.type},
        "destination": {"id": objective.id, "type": objective.type},
        "context": None,
      },
    })
    self.assertStatus(response, result_status)
