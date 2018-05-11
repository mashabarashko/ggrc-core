# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for WithAction mixin"""

import copy

from ggrc.models import all_models

from integration.ggrc import api_helper

from integration.ggrc import TestCase
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories
from integration.ggrc.query_helper import WithQueryApi


def _get_relationship(type_, assessment_id):
  """Helper function for gettint the relationship object"""
  return all_models.Relationship.query.filter(
      all_models.Relationship.source_type == type_,
      all_models.Relationship.source_id == assessment_id,
  ).order_by(all_models.Relationship.id.desc()).first()


class TestDocumentWithActionMixin(TestCase, WithQueryApi):
  """Test case for WithAction mixin and Document actions."""
  # pylint: disable=invalid-name,too-many-public-methods

  def setUp(self):
    super(TestDocumentWithActionMixin, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  def test_empty_list_assessment(self):
    """Test actions with empty lists on assessments."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"add_related": [],
                                                     "remove_related": []}})
    self.assert200(response)

  def test_empty_list_issue(self):
    """Test actions with empty lists on issues."""
    issue = factories.IssueFactory()
    response = self.api.put(issue, {"actions": {"add_related": [],
                                                "remove_related": []}})
    self.assert200(response)

  def test_add_url(self):
    """Test add url action."""
    assessment = factories.AssessmentFactory()
    context = factories.ContextFactory(related_object=assessment)
    assessment.context = context
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": None,
            "type": "Document",
            "link": "google.com",
            "title": "google.com",
            "document_type": all_models.Document.URL,
        }
    ]}})
    self.assert200(response)

    relationship = _get_relationship(
        "Assessment", response.json["assessment"]["id"])
    self.assertIsNotNone(relationship)
    document = all_models.Document.query.get(relationship.destination_id)
    self.assertEqual(document.link, "google.com")
    self.assertEqual(document.document_type, all_models.Document.URL)
    self.assertEqual(document.context_id, assessment.context_id)

  def test_map_document_assessment(self):
    """Test map document action on assessment."""
    assessment = factories.AssessmentFactory()
    document = factories.DocumentFactory()
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": document.id,
            "type": "Document",
        }
    ]}})
    self.assert200(response)

    relationship = _get_relationship(
        "Assessment", response.json["assessment"]["id"])
    self.assertEqual(relationship.destination_id, document.id)
    self.assertEqual(relationship.source_id, assessment.id)

  def test_map_document_issue(self):
    """Test map document action on issue."""
    issue = factories.IssueFactory()
    document = factories.DocumentFactory()
    response = self.api.put(issue, {"actions": {"add_related": [
        {
            "id": document.id,
            "type": "Document",
        }
    ]}})
    self.assert200(response)

    relationship = _get_relationship(
        "Issue", response.json["issue"]["id"])
    self.assertEqual(relationship.destination_id, document.id)
    self.assertEqual(relationship.source_id, issue.id)

  def test_wrong_add_url(self):
    """Test wrong add url action."""
    assessment = factories.AssessmentFactory()
    wrong_params = {
        "id": None,
        "type": "Document",
    }
    response = self.api.put(assessment, {"actions": {"add_related": [
        wrong_params
    ]}})
    self.assert400(response)

    wrong_params["document_type"] = "Evidence URL"
    response = self.api.put(assessment, {"actions": {"add_related": [
        wrong_params
    ]}})
    self.assert400(response)

    wrong_params["link"] = "google.com"
    response = self.api.put(assessment, {"actions": {"add_related": [
        wrong_params
    ]}})
    self.assert400(response)

  def test_wrong_add_action_assessment(self):
    """Test wrong add action on assessment."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"add_related": [{}]}})
    self.assert400(response)

    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "type": "Document",
        }
    ]}})
    self.assert400(response)

    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": None,
        }
    ]}})
    self.assert400(response)

  def test_wrong_add_action_issue(self):
    """Test wrong add action on issue."""
    issue = factories.IssueFactory()
    response = self.api.put(issue, {"actions": {"add_related": [{}]}})
    self.assert400(response)

    response = self.api.put(issue, {"actions": {"add_related": [
        {
            "type": "Document",
        }
    ]}})
    self.assert400(response)

    response = self.api.put(issue, {"actions": {"add_related": [
        {
            "id": None,
        }
    ]}})
    self.assert400(response)

    response = self.api.put(issue, {"actions": {"add_related": [
        {
            "id": None,
            "type": "Document",
        }
    ]}})
    self.assert400(response)

  def test_unmap_document_as_dst_assessment(self):
    """Test unmapping of documents set as relationship destination on
    assessment."""
    assessment = factories.AssessmentFactory()
    document = factories.DocumentFactory()
    rel_id = factories.RelationshipFactory(source=assessment,
                                           destination=document).id
    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": document.id,
            "type": "Document",
        }
    ]}})
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel_id)
    self.assertIsNone(relationship)

  def test_unmap_document_as_dst_issue(self):
    """Test unmapping of documents set as relationship destination on
    issue."""
    issue = factories.IssueFactory()
    document = factories.DocumentFactory()
    rel_id = factories.RelationshipFactory(source=issue,
                                           destination=document).id
    response = self.api.put(issue, {"actions": {"remove_related": [
        {
            "id": document.id,
            "type": "Document",
        }
    ]}})
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel_id)
    self.assertIsNone(relationship)

  def test_unmap_document_as_src_assessment(self):
    """Test unmapping of documents set as relationship source on
    assessment."""
    assessment = factories.AssessmentFactory()
    document = factories.DocumentFactory()
    rel_id = factories.RelationshipFactory(destination=assessment,
                                           source=document).id
    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": document.id,
            "type": "Document",
        }
    ]}})
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel_id)
    self.assertIsNone(relationship)

  def test_unmap_document_as_src_issue(self):
    """Test unmapping of documents set as relationship source on
    issue."""
    issue = factories.IssueFactory()
    document = factories.DocumentFactory()
    rel_id = factories.RelationshipFactory(destination=issue,
                                           source=document).id
    response = self.api.put(issue, {"actions": {"remove_related": [
        {
            "id": document.id,
            "type": "Document",
        }
    ]}})
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel_id)
    self.assertIsNone(relationship)

  def test_wrong_remove_action_assessment(self):
    """Test wrong remove action on assessment."""
    assessment = factories.AssessmentFactory()
    document_id = factories.DocumentFactory().id

    response = self.api.put(assessment, {"actions": {"remove_related": [{}]}})
    self.assert400(response)

    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": document_id,
        }
    ]}})
    self.assert400(response)

    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "type": "Document",
        }
    ]}})
    self.assert400(response)

    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": None,
            "type": "Document",
        }
    ]}})
    self.assert400(response)

  def test_wrong_remove_action_issue(self):
    """Test wrong remove action on issue."""
    issue = factories.IssueFactory()
    document_id = factories.DocumentFactory().id

    response = self.api.put(issue, {"actions": {"remove_related": [{}]}})
    self.assert400(response)

    response = self.api.put(issue, {"actions": {"remove_related": [
        {
            "id": document_id,
        }
    ]}})
    self.assert400(response)

    response = self.api.put(issue, {"actions": {"remove_related": [
        {
            "type": "Document",
        }
    ]}})
    self.assert400(response)

    response = self.api.put(issue, {"actions": {"remove_related": [
        {
            "id": None,
            "type": "Document",
        }
    ]}})
    self.assert400(response)

  def test_unmap_nonexistent_url_assessment(self):
    """Test unmap nonexistent url action on assessment."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": 0,
            "type": "Document",
        }
    ]}})
    self.assert400(response)

  def test_unmap_nonexistent_url_issue(self):
    """Test unmap nonexistent url action on issue."""
    issue = factories.IssueFactory()
    response = self.api.put(issue, {"actions": {"remove_related": [
        {
            "id": 0,
            "type": "Document",
        }
    ]}})
    self.assert400(response)

  def test_wrong_unmap_url_assessment(self):
    """Test wrong unmap url action on assessment."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "type": "Document",
        }
    ]}})
    self.assert400(response)

  def test_wrong_unmap_url_issue(self):
    """Test wrong unmap url action on issue."""
    issue = factories.IssueFactory()
    response = self.api.put(issue, {"actions": {"remove_related": [
        {
            "type": "Document",
        }
    ]}})
    self.assert400(response)

  def test_add_evidence(self):
    """Test add evidence action."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": None,
            "type": "Document",
            "document_type": "EVIDENCE",
            "title": "evidence1",
            "link": "google.com",

        }
    ]}})
    self.assert200(response)

    relationship = _get_relationship(
        "Assessment", response.json["assessment"]["id"])
    self.assertIsNotNone(relationship)
    document = all_models.Document.query.get(relationship.destination_id)
    self.assertEqual(document.link, "google.com")
    self.assertEqual(document.title, "evidence1")
    self.assertEqual(document.document_type, all_models.Document.ATTACHMENT)

  def test_wrong_add_evidence(self):
    """Test wrong add evidence action."""
    assessment = factories.AssessmentFactory()
    proper_values = {
        "id": None,
        "type": "Document",
        "document_type": "EVIDENCE",
        "title": "evidence1",
        "link": "google.com",
    }

    wrong_values = copy.copy(proper_values)
    del wrong_values["title"]
    response = self.api.put(assessment, {"actions": {"add_related":
                                         [wrong_values]}})
    self.assert400(response)

    wrong_values = copy.copy(proper_values)
    del wrong_values["link"]
    response = self.api.put(assessment, {"actions": {"add_related":
                                         [wrong_values]}})
    self.assert400(response)

    wrong_values = copy.copy(proper_values)
    wrong_values["document_type"] = "EVDNCE"
    response = self.api.put(assessment, {"actions": {"add_related":
                                         [wrong_values]}})
    self.assert400(response)

  def test_status_change_document(self):
    """Test auto status change after add document action"""
    assessment = factories.AssessmentFactory(
        status=all_models.Assessment.FINAL_STATE)
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": None,
            "type": "Document",
            "link": "google.com",
            "title": "google.com",
            "document_type": "URL",
        }
    ]}})
    self.assert200(response)
    self.assertEqual(response.json["assessment"]["status"],
                     all_models.Assessment.PROGRESS_STATE)

  def test_put_without_actions_assessment(self):
    """Test assessment put without actions on assessment."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"description": "test"})
    self.assert200(response)

  def test_put_without_actions_issue(self):
    """Test assessment put without actions on issue."""
    issue = factories.IssueFactory()
    response = self.api.put(issue, {"description": "test"})
    self.assert200(response)

  def test_document_indexing(self):
    """Test document_indexing"""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": None,
            "type": "Document",
            "link": "google.com",
            "title": "google.com",
            "document_type": "URL",
        }
    ]}})
    self.assert200(response)

    assessments_by_url = self.simple_query(
        "Assessment",
        expression=["evidence url", "~", "google.com"]
    )
    self.assertEqual(len(assessments_by_url), 1)

    relationship = _get_relationship(
        "Assessment", response.json["assessment"]["id"])

    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": relationship.destination_id,
            "type": "Document",
        }
    ]}})

    self.assert200(response)

    assessments_by_url = self.simple_query(
        "Assessment",
        expression=["evidence url", "~", "google.com"]
    )
    self.assertFalse(assessments_by_url)


class TestCommentWithActionMixin(TestCase):
  """Test case for WithAction mixin and Comment actions."""

  def setUp(self):
    super(TestCommentWithActionMixin, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  def test_add_comment(self):
    """Test add comment action."""
    generator = ObjectGenerator()

    _, reader = generator.generate_person(user_role="Administrator")
    self.api.set_user(reader)

    assessment = factories.AssessmentFactory()
    context = factories.ContextFactory(related_object=assessment)
    assessment.context = context

    acrs = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Assessment",
        all_models.AccessControlRole.name.in_(["Assignees", "Creators"]),
    )

    for acr in acrs:
      factories.AccessControlListFactory(
          ac_role=acr,
          object=assessment,
          person=reader
      )

    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "type": "Comment",
            "description": "comment",
            "assignee_type": None,
            "context": None,
            "custom_attribute_revision_upd": None,
        }
    ]}})
    self.assert200(response)
    # last relationship id (newly created relationship)
    relationship = _get_relationship(
        "Assessment", response.json["assessment"]["id"])
    self.assertIsNotNone(relationship)
    comment = all_models.Comment.query.get(relationship.destination_id)
    self.assertEqual(comment.description, "comment")
    self.assertEqual(comment.assignee_type, "Assignees,Creators")
    self.assertEqual(comment.context_id, assessment.context_id)

  def test_add_custom_comment(self):
    """Test add custom attribute comment action."""
    assessment = factories.AssessmentFactory()
    ca_def = factories.CustomAttributeDefinitionFactory(
        title="def1",
        definition_type="assessment",
        attribute_type="Dropdown",
        multi_choice_options="no,yes",
    )
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "type": "Comment",
            "description": "comment",
            "assignee_type": None,
            "context": None,
            "custom_attribute_revision_upd": {
                "custom_attribute_definition": {
                    "id": ca_def.id
                },
                "attributable": {
                    "id": assessment.id,
                    "type": "Assessment",
                },
            },
        }
    ]}})
    self.assert200(response)
    relationship = _get_relationship(
        "Assessment", response.json["assessment"]["id"])
    self.assertIsNotNone(relationship)
    comment = all_models.Comment.query.get(relationship.destination_id)
    self.assertEqual(comment.description, "comment")
    self.assertEqual(comment.custom_attribute_definition_id, ca_def.id)

  def test_wrong_comment(self):
    """Test add custom attribute comment action without description."""
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      ca_def = factories.CustomAttributeDefinitionFactory(
          title="def1",
          definition_type="assessment",
          attribute_type="Dropdown",
          multi_choice_options="no,yes",
      )
    data = {
        u"type": u"Comment",
        u"assignee_type": None,
        u"context": None,
        u"custom_attribute_revision_upd": {
            u"custom_attribute_definition": {
                u"id": int(ca_def.id)
            },
            u"attributable": {
                u"id": int(assessment.id),
                u"type": u"Assessment",
            },
        },
    }
    response = self.api.put(assessment, {"actions": {"add_related": [data]}})
    self.assert400(response)

    err = u"Fields {} are missing for action: {!r}".format("description", data)
    self.assertEqual(response.json.get("message"), err)

  def test_wrong_add_comment(self):
    """Test wrong add comment action."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "type": "Comment",
        }
    ]}})
    self.assert400(response)

  def test_remove_comment(self):
    """Test remove comment action."""
    assessment = factories.AssessmentFactory()
    comment = factories.CommentFactory(description="123")
    rel_id = factories.RelationshipFactory(source=assessment,
                                           destination=comment).id
    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": comment.id,
            "type": "Comment",
        }
    ]}})
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel_id)
    self.assertIsNone(relationship)


def _create_snapshot():
  """Create snapshot for test"""
  audit = factories.AuditFactory()
  assessment = factories.AssessmentFactory(audit=audit)
  context = factories.ContextFactory(related_object=assessment)
  assessment.context = context
  factories.RelationshipFactory(source=audit, destination=assessment)
  control = factories.ControlFactory(description='control-9')
  revision = all_models.Revision.query.filter(
      all_models.Revision.resource_id == control.id,
      all_models.Revision.resource_type == control.__class__.__name__
  ).order_by(
      all_models.Revision.id.desc()
  ).first()
  snapshot = factories.SnapshotFactory(
      parent=audit,
      child_id=control.id,
      child_type=control.__class__.__name__,
      revision_id=revision.id
  )
  return assessment, snapshot


class TestSnapshotWithActionMixin(TestCase, WithQueryApi):
  """Test case for WithAction mixin and Snapshot actions."""

  def setUp(self):
    super(TestSnapshotWithActionMixin, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  def test_add_snapshot(self):
    """Test add snapshot action."""
    assessment, snapshot = _create_snapshot()
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": snapshot.id,
            "type": "Snapshot",
        }
    ]}})
    self.assert200(response)
    relationship = _get_relationship(
        "Assessment", response.json["assessment"]["id"])
    self.assertIsNotNone(relationship)
    self.assertEqual(relationship.destination_id, snapshot.id)
    self.assertEqual(relationship.destination_type, "Snapshot")
    self.assertEqual(relationship.context_id, assessment.context_id)

    audits = self.simple_query('Audit',
                               expression=["description", "~", "'control-9'"])
    self.assertFalse(audits)

  def test_wrong_add_snapshot(self):
    """Test wrong add snapshot action."""
    assessment = factories.AssessmentFactory()
    response = self.api.put(assessment, {"actions": {"add_related": [
        {
            "id": None,
            "type": "Snapshot",
        }
    ]}})
    self.assert400(response)

  def test_remove_snapshot(self):
    """Test remove snapshot action."""
    assessment, snapshot = _create_snapshot()
    rel_id = factories.RelationshipFactory(source=assessment,
                                           destination=snapshot).id
    response = self.api.put(assessment, {"actions": {"remove_related": [
        {
            "id": snapshot.id,
            "type": "Snapshot",
        }
    ]}})
    self.assert200(response)
    snapshot = all_models.Relationship.query.get(rel_id)
    self.assertIsNone(snapshot)


class TestMultiplyActions(TestCase, WithQueryApi):
  """Test case for WithAction mixin with multiply actions."""

  def setUp(self):
    super(TestMultiplyActions, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  def test_multiply_actions(self):
    """Test multiply actions"""
    assessment = factories.AssessmentFactory()
    doc_map = factories.DocumentFactory(link="google1.com")
    doc_del = factories.DocumentFactory(link="google2.com")
    factories.RelationshipFactory(source=assessment,
                                  destination=doc_del)

    ca_def = factories.CustomAttributeDefinitionFactory(
        title="def1",
        definition_type="assessment",
        definition_id=assessment.id,
        attribute_type="Dropdown",
        multi_choice_options="no,yes",
        multi_choice_mandatory="0,3"
    )
    ca_val = factories.CustomAttributeValueFactory(
        custom_attribute=ca_def,
        attributable=assessment,
        attribute_value="no"
    )
    response = self.api.put(assessment, {
        "custom_attribute_values": [
            {
                "id": ca_val.id,
                "custom_attribute_id": ca_def.id,
                "attribute_value": "yes",
                "type": "CustomAttributeValue",
            }],
        "actions": {"add_related": [
            {
                "id": None,
                "type": "Document",
                "document_type": "EVIDENCE",
                "title": "evidence1",
                "link": "google3.com",
            },
            {
                "id": doc_map.id,
                "type": "Document",
            },
            {
                "type": "Comment",
                "description": "comment1",
                "assignee_type": None,
                "context": None,
                "custom_attribute_revision_upd": {
                    "custom_attribute_definition": {
                        "id": ca_def.id
                    },
                    "attributable": {
                        "id": assessment,
                        "type": "Assessment",
                    },
                },
            }
        ], "remove_related": [
            {
                "id": doc_del.id,
                "type": "Document",
            }]}})
    self.assert200(response)

    preconditions_failed = response.json["assessment"]["preconditions_failed"]
    self.assertIs(preconditions_failed, True)

    assessment_by_url = self.simple_query(
        "Assessment",
        expression=["evidence url", "~", "google1.com"]
    )
    self.assertEqual(len(assessment_by_url), 1)
    assessment_by_url = self.simple_query(
        "Assessment",
        expression=["evidence url", "~", "google2.com"]
    )
    self.assertFalse(assessment_by_url)
    assessment_by_evidence = self.simple_query(
        "Assessment",
        expression=["evidence file", "~", "google3.com"]
    )
    self.assertEqual(len(assessment_by_evidence), 1)
    assessment_by_comment = self.simple_query(
        "Assessment",
        expression=["comment", "~", "comment1"]
    )
    self.assertEqual(len(assessment_by_comment), 1)
