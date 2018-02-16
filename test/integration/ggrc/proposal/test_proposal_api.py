# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for proposal api."""

import collections
import json

import ddt

from ggrc import utils
from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


@ddt.ddt
class TestProposalApi(TestCase):
  """Test case for proposal api."""

  def setUp(self):
    super(TestProposalApi, self).setUp()
    self.api = Api()
    self.client.get("/login")

  def test_simple_get_proposal(self):
    """Test simple get proposal."""
    with factories.single_commit():
      control = factories.ControlFactory()
      proposal = factories.ProposalFactory(instance=control,
                                           content={"field": "a"},
                                           agenda="agenda content")
    instance_dict = {"id": control.id, "type": control.type}
    resp = self.api.get(all_models.Proposal, proposal.id)
    self.assert200(resp)
    self.assertIn("proposal", resp.json)
    data = resp.json["proposal"]
    self.assertIn("content", data)
    self.assertIn("instance", data)
    self.assertIn("agenda", data)
    self.assertDictEqual(instance_dict, data["instance"])
    self.assertDictEqual({"field": "a"}, data["content"])
    self.assertEqual("agenda content", data["agenda"])

  def test_simple_create_proposal(self):
    """Test simple create proposal."""
    new_title = "2"
    control = factories.ControlFactory(title="1")
    control_id = control.id
    control.title = new_title
    self.assertEqual(0, len(control.comments))
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": control.log_json(),
            "agenda": "update title from 1 to 2",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("fields", control.proposals[0].content)
    self.assertEqual({"title": "2"}, control.proposals[0].content["fields"])
    self.assertEqual(1, len(control.comments))

  def test_simple_apply_status(self):
    """Test simple apply status."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      proposal = factories.ProposalFactory(
          instance=control,
          content={"fields": {"title": "2"}},
          agenda="agenda content")
    control_id = control.id
    proposal_id = proposal.id
    self.assertEqual(proposal.STATES.PROPOSED, proposal.status)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    self.assertEqual(0, len(control.comments))
    resp = self.api.put(
        proposal,
        {
            "proposal": {
                "status": proposal.STATES.APPLIED,
                "apply_reason": "approved",
            }
        })
    self.assert200(resp)
    control = all_models.Control.query.get(control_id)
    proposal = all_models.Proposal.query.get(proposal_id)
    self.assertEqual(proposal.STATES.APPLIED, proposal.status)
    self.assertEqual("2", control.title)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(2, len(revisions))
    self.assertEqual("2", revisions[-1].content['title'])
    self.assertEqual(1, len(control.comments))

  def test_simple_decline_status(self):
    """Test simple decline status."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      proposal = factories.ProposalFactory(
          instance=control,
          content={"fields": {"title": "2"}},
          agenda="agenda content")
    control_id = control.id
    proposal_id = proposal.id
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(proposal.STATES.PROPOSED, proposal.status)
    self.assertEqual(1, len(revisions))
    self.assertEqual(0, len(control.comments))
    resp = self.api.put(
        proposal,
        {
            "proposal": {
                "status": proposal.STATES.DECLINED,
                "decline_reason": "declined bla",
            }
        })
    self.assert200(resp)
    control = all_models.Control.query.get(control_id)
    proposal = all_models.Proposal.query.get(proposal_id)
    self.assertEqual(proposal.STATES.DECLINED, proposal.status)
    self.assertEqual("1", control.title)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    self.assertEqual(1, len(control.comments))

  def test_proposal_for_acl(self):
    """Test simple add acl proposal."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      role = factories.AccessControlRoleFactory(name="role")
      person = factories.PersonFactory()
    control_id = control.id
    role_id = unicode(role.id)
    person_id = person.id
    control_content = control.log_json()
    control_content["access_control_list"] = [
        {"ac_role_id": role_id, "person": {"type": "Person", "id": person.id}}
    ]
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": control_content,
            "agenda": "update access control roles",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("access_control_list", control.proposals[0].content)
    acl = control.proposals[0].content["access_control_list"]
    self.assertIn(role_id, acl)
    role = control.proposals[0].content["access_control_list"][role_id]
    person = all_models.Person.query.get(person_id)
    self.assertEqual(
        {
            "added": [{"id": person_id, "email": person.email}],
            "deleted": [],
        },
        role)
    self.assertEqual(1, len(control.comments))

  def test_proposal_delete_acl(self):
    """Test simple delete acl proposal."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      role = factories.AccessControlRoleFactory(name="role")
      person = factories.PersonFactory()
      factories.AccessControlListFactory(
          person=person,
          ac_role=role,
          object=control,
      )
    with factories.single_commit():
      latest_revision = all_models.Revision.query.filter(
          all_models.Revision.resource_id == control.id,
          all_models.Revision.resource_type == control.type
      ).order_by(
          all_models.Revision.created_at.desc()
      ).first()
      latest_revision.content = control.log_json()

    control_id = control.id
    role_id = unicode(role.id)
    person_id = person.id
    control_content = control.log_json()
    control_content["access_control_list"] = []
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": control_content,
            "agenda": "delete access control roles",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("access_control_list", control.proposals[0].content)
    acl = control.proposals[0].content["access_control_list"]
    self.assertIn(role_id, acl)
    role = control.proposals[0].content["access_control_list"][role_id]
    person = all_models.Person.query.get(person_id)
    self.assertEqual(
        {
            "added": [],
            "deleted": [{"id": person_id, "email": person.email}],
        },
        role)
    self.assertEqual(1, len(control.comments))

  def test_apply_acl(self):  # pylint: disable=too-many-locals
    """Test simple apply acl proposal."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      role_1 = factories.AccessControlRoleFactory(
          name="role_1", object_type="Control")
      role_2 = factories.AccessControlRoleFactory(
          name="role_2", object_type="Control")
      role_3 = factories.AccessControlRoleFactory(
          name="role_3", object_type="Control")
      role_4 = factories.AccessControlRoleFactory(
          name="role_4", object_type="Control")
      role_5 = factories.AccessControlRoleFactory(
          name="role_5", object_type="Control")
      person_1 = factories.PersonFactory()
      person_2 = factories.PersonFactory()
      person_3 = factories.PersonFactory()
      factories.AccessControlListFactory(
          person=person_1,
          ac_role=role_1,
          object=control,
      )
      factories.AccessControlListFactory(
          person=person_2,
          ac_role=role_2,
          object=control,
      )
      factories.AccessControlListFactory(
          person=person_3,
          ac_role=role_3,
          object=control,
      )
      for person in [person_1, person_2, person_3]:
        factories.AccessControlListFactory(
            person=person,
            ac_role=role_4,
            object=control,
        )

    with factories.single_commit():
      proposal = factories.ProposalFactory(
          instance=control,
          content={
              "access_control_list": {
                  role_1.id: {
                      "added": [{"id": person_2.id, "email": person_2.email}],
                      "deleted": []
                  },
                  role_2.id: {
                      "added": [{"id": person_1.id, "email": person_1.email}],
                      "deleted": [{"id": person_2.id, "email": person_2.email}]
                  },
                  role_3.id: {
                      "added": [{"id": person_3.id, "email": person_3.email}],
                      "deleted": [{"id": person_2.id, "email": person_2.email}]
                  },
                  role_4.id: {
                      "added": [],
                      "deleted": [{"id": person_1.id, "email": person_1.email},
                                  {"id": person_2.id, "email": person_2.email},
                                  {"id": person_3.id, "email": person_3.email}]
                  },
                  role_5.id: {
                      "added": [{"id": person_1.id, "email": person_1.email},
                                {"id": person_2.id, "email": person_2.email},
                                {"id": person_3.id, "email": person_3.email}],
                      "deleted": [],
                  },
              }
          },
          agenda="agenda content")
    control_id = control.id
    person_1_id = person_1.id
    person_2_id = person_2.id
    person_3_id = person_3.id
    role_1_id = role_1.id
    role_2_id = role_2.id
    role_3_id = role_3.id
    role_4_id = role_4.id
    role_5_id = role_5.id
    self.assertEqual(proposal.STATES.PROPOSED, proposal.status)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    resp = self.api.put(
        proposal, {"proposal": {"status": proposal.STATES.APPLIED}})
    self.assert200(resp)
    control = all_models.Control.query.get(control_id)
    result_dict = collections.defaultdict(set)
    for acl in control.access_control_list:
      result_dict[acl.ac_role_id].add(acl.person_id)
    self.assertEqual({person_1_id, person_2_id}, result_dict[role_1_id])
    self.assertEqual({person_1_id}, result_dict[role_2_id])
    self.assertEqual({person_3_id}, result_dict[role_3_id])
    self.assertEqual(set([]), result_dict[role_4_id])
    self.assertEqual({person_1_id, person_2_id, person_3_id},
                     result_dict[role_5_id])

  def test_change_cad(self):
    """Test create proposal with change CAVs."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      cad = factories.CustomAttributeDefinitionFactory(
          definition_type="control")
      factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=control,
          attribute_value="123")
    control_id = control.id
    cad_id = cad.id
    data = control.log_json()
    del data["custom_attributes"]
    data["custom_attribute_values"][0]["attribute_value"] = "321"
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": data,
            "agenda": "update cav",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("custom_attribute_values", control.proposals[0].content)
    self.assertEqual({unicode(cad_id): {"attribute_value": u"321",
                                        "attribute_object": None,
                                        "remove_cav": False}},
                     control.proposals[0].content["custom_attribute_values"])
    self.assertEqual(1, len(control.comments))

  @ddt.data(True, False)
  def test_apply_cad(self, remove_cav):
    """Test apply proposal with change CAVs."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      cad = factories.CustomAttributeDefinitionFactory(
          definition_type="control")
    control_id = control.id
    proposal = factories.ProposalFactory(
        instance=control,
        content={
            "custom_attribute_values": {
                cad.id: {
                    "attribute_value": "321",
                    "attribute_object": None,
                    "remove_cav": remove_cav,
                },
            },
        },
        agenda="agenda content")
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    resp = self.api.put(
        proposal, {"proposal": {"status": proposal.STATES.APPLIED}})
    self.assert200(resp)
    control = all_models.Control.query.get(control_id)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(2, len(revisions))
    self.assertEqual(
        "321",
        control.custom_attribute_values[0].attribute_value)

  @ddt.data(True, False)
  def test_apply_mapping_cad(self, remove_cav):
    """Test apply mapping CAVs proposal."""
    with factories.single_commit():
      control = factories.ControlFactory(title="1")
      cad = factories.CustomAttributeDefinitionFactory(
          definition_type="control",
          attribute_type="Map:Person"
      )
      person = factories.PersonFactory()
      cav = factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=control,
          attribute_object_id=person.id,
          attribute_value="Person",
      )
    self.assertEqual(person,
                     control.custom_attribute_values[0].attribute_object)
    control_id = control.id
    proposal = factories.ProposalFactory(
        instance=control,
        content={
            "custom_attribute_values": {
                cad.id: {
                    "attribute_value": "Person",
                    "attribute_object": None,
                    "remove_cav": remove_cav,
                },
            },
        },
        agenda="agenda content")
    resp = self.api.put(
        proposal, {"proposal": {"status": proposal.STATES.APPLIED}})
    self.assert200(resp)
    control = all_models.Control.query.get(control_id)
    if remove_cav:
      self.assertFalse(control.custom_attribute_values)
    else:
      cav = control.custom_attribute_values[0]
      self.assertEqual("Person", cav.attribute_value)
      self.assertIsNone(cav.attribute_object_id)

  def test_change_mapping(self):
    """Test create mapping proposal."""
    setuped_kind, update_kind = all_models.Option.query.filter(
        all_models.Option.role == "control_kind"
    )[:2]
    control = factories.ControlFactory(title="1", kind=setuped_kind)
    control_id = control.id
    data = control.log_json()
    update_kind_json = update_kind.log_json()
    data["kind"] = update_kind_json
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": data,
            "agenda": "update kind",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("mapping_fields", control.proposals[0].content)
    self.assertIn("kind", control.proposals[0].content["mapping_fields"])
    self.assertEqual(json.loads(utils.as_json(update_kind_json)),
                     control.proposals[0].content["mapping_fields"]["kind"])
    self.assertEqual(1, len(control.comments))

  def test_apply_mapping(self):
    """Test apply mapping proposal."""
    setuped_kind, update_kind = all_models.Option.query.filter(
        all_models.Option.role == "control_kind"
    )[:2]
    with factories.single_commit():
      control = factories.ControlFactory(title="1", kind=setuped_kind)
      proposal = factories.ProposalFactory(
          instance=control,
          content={
              "mapping_fields": {
                  "kind": {
                      "id": update_kind.id,
                      "type": update_kind.type,
                  },
              },
          },
          agenda="agenda content")
    control_id = control.id
    proposal_id = proposal.id
    update_kind_id = update_kind.id
    self.assertEqual(proposal.STATES.PROPOSED, proposal.status)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    self.assertEqual(0, len(control.comments))
    resp = self.api.put(
        proposal,
        {
            "proposal": {
                "status": proposal.STATES.APPLIED,
                "apply_reason": "approved",
            }
        })
    self.assert200(resp)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(all_models.Option.query.get(update_kind_id), control.kind)
    proposal = all_models.Proposal.query.get(proposal_id)
    self.assertEqual(proposal.STATES.APPLIED, proposal.status)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(2, len(revisions))
    self.assertIn("kind", revisions[-1].content)
    self.assertIn("id", revisions[-1].content["kind"])
    self.assertEqual(update_kind_id, revisions[-1].content["kind"]["id"])
    self.assertEqual(1, len(control.comments))

  def test_change_mapping_to_empty(self):
    """Test create empty mapping proposal."""
    setuped_kind = all_models.Option.query.filter(
        all_models.Option.role == "control_kind"
    ).first()
    control = factories.ControlFactory(title="1", kind=setuped_kind)
    control.kind = None
    control_id = control.id
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": control.log_json(),
            "agenda": "update kind",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("mapping_fields", control.proposals[0].content)
    self.assertIn("kind", control.proposals[0].content["mapping_fields"])
    self.assertIsNone(control.proposals[0].content["mapping_fields"]["kind"])
    self.assertEqual(1, len(control.comments))

  def test_apply_empty_mapping(self):
    """Test apply empty mapping proposal."""
    setuped_kind = all_models.Option.query.filter(
        all_models.Option.role == "control_kind"
    ).first()
    with factories.single_commit():
      control = factories.ControlFactory(title="1", kind=setuped_kind)
      proposal = factories.ProposalFactory(
          instance=control,
          content={"mapping_fields": {"kind": None}},
          agenda="agenda content")
    control_id = control.id
    proposal_id = proposal.id
    self.assertEqual(proposal.STATES.PROPOSED, proposal.status)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    self.assertEqual(0, len(control.comments))
    resp = self.api.put(
        proposal,
        {
            "proposal": {
                "status": proposal.STATES.APPLIED,
                "apply_reason": "approved",
            }
        })
    self.assert200(resp)
    control = all_models.Control.query.get(control_id)
    self.assertIsNone(control.kind)
    proposal = all_models.Proposal.query.get(proposal_id)
    self.assertEqual(proposal.STATES.APPLIED, proposal.status)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(2, len(revisions))
    self.assertIn("kind", revisions[-1].content)
    self.assertIsNone(revisions[-1].content["kind"])
    self.assertEqual(1, len(control.comments))

  def test_change_mapping_list(self):
    """Test create mapping list proposal."""
    with factories.single_commit():
      cat = factories.ControlCategoryFactory()
      control = factories.ControlFactory(title="1")
    data = control.log_json()
    control_id = control.id
    data["categories"] = [{"id": cat.id, "type": cat.type}]
    cat_id = cat.id
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": data,
            "agenda": "update categories",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("mapping_list_fields", control.proposals[0].content)
    fields = control.proposals[0].content["mapping_list_fields"]
    self.assertIn("categories", fields)
    self.assertEqual(
        {"added": [{"id": cat_id, "type": "ControlCategory"}],
         "deleted": []},
        fields["categories"])
    self.assertEqual(1, len(control.comments))

  def test_change_empty_mapping_list(self):
    """Test create mapping list proposal to empty."""
    with factories.single_commit():
      category = factories.ControlCategoryFactory()
      control = factories.ControlFactory(categories=[category])
    data = control.log_json()
    category_id = category.id
    control_id = control.id
    data["categories"] = []
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": control.id,
                "type": control.type,
            },
            # "content": {"123": 123},
            "full_instance_content": data,
            "agenda": "update categories",
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    control = all_models.Control.query.get(control_id)
    category = all_models.ControlCategory.query.get(category_id)
    self.assertEqual(1, len(control.proposals))
    self.assertIn("mapping_list_fields", control.proposals[0].content)
    fields = control.proposals[0].content["mapping_list_fields"]
    self.assertIn("categories", fields)
    self.assertEqual(
        {"added": [],
         "deleted": [json.loads(utils.as_json(category.log_json()))]},
        fields["categories"])
    self.assertEqual(1, len(control.comments))

  def test_apply_empty_mapping_list(self):
    """Test apply mapping list proposal to empty."""
    with factories.single_commit():
      category = factories.ControlCategoryFactory()
      control = factories.ControlFactory()
      control.categories.append(category)
    control_id = control.id
    category_id = category.id
    with factories.single_commit():
      proposal = factories.ProposalFactory(
          instance=control,
          content={
              "mapping_list_fields": {
                  "categories": {
                      "added": [],
                      "deleted": [
                          {"id": category_id, "type": "ControlCategory"},
                      ]
                  }
              }
          },
          agenda="agenda content")
    proposal_id = proposal.id
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    resp = self.api.put(
        proposal,
        {
            "proposal": {
                "status": proposal.STATES.APPLIED,
                "apply_reason": "approved",
            }
        })
    self.assertEqual(200, resp.status_code)
    control = all_models.Control.query.get(control_id)
    proposal = all_models.Proposal.query.get(proposal_id)
    self.assertEqual(proposal.STATES.APPLIED, proposal.status)
    control = all_models.Control.query.get(control_id)
    self.assertEqual([], control.categories)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(2, len(revisions))
    self.assertEqual(1, len(control.comments))

  def test_apply_mapping_list(self):
    """Test apply mapping list proposal."""
    with factories.single_commit():
      category = factories.ControlCategoryFactory()
      control = factories.ControlFactory()
    control_id = control.id
    category_id = category.id
    with factories.single_commit():
      proposal = factories.ProposalFactory(
          instance=control,
          content={
              "mapping_list_fields": {
                  "categories": {
                      "deleted": [],
                      "added": [
                          {"id": category_id, "type": "ControlCategory"},
                      ]
                  }
              }
          },
          agenda="agenda content")
    proposal_id = proposal.id
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(1, len(revisions))
    resp = self.api.put(
        proposal,
        {
            "proposal": {
                "status": proposal.STATES.APPLIED,
                "apply_reason": "approved",
            }
        })
    self.assertEqual(200, resp.status_code)
    control = all_models.Control.query.get(control_id)
    proposal = all_models.Proposal.query.get(proposal_id)
    self.assertEqual(proposal.STATES.APPLIED, proposal.status)
    control = all_models.Control.query.get(control_id)
    self.assertEqual([all_models.ControlCategory.query.get(category_id)],
                     control.categories)
    revisions = all_models.Revision.query.filter(
        all_models.Revision.resource_type == control.type,
        all_models.Revision.resource_id == control.id
    ).all()
    self.assertEqual(2, len(revisions))
    self.assertEqual(1, len(control.comments))
    comment = control.comments[0]
    self.assertEqual(proposal, comment.initiator_instance)
