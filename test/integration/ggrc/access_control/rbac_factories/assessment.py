# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Assessment RBAC Factory."""

from ggrc.models import all_models, get_model

from integration.ggrc import Api, TestCase, generator
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class AssessmentRBACFactory(base.BaseRBACFactory):
  """Assessment RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Assessment permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    self.setup_program_scope(user_id, acr, parent)

    self.api = Api()
    self.objgen = generator.ObjectGenerator()
    self.objgen.api = self.api

    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Assessment object."""
    return self.api.post(all_models.Assessment, {
        "assessment": {
            "title": "New Assessment",
            "context": None,
            "audit": {"id": self.audit_id},
        },
    })

  def generate(self):
    """Generate new Assessment object."""
    with factories.single_commit():
      control = factories.ControlFactory()
      template_id = factories.AssessmentTemplateFactory().id
    audit = all_models.Audit.query.get(self.audit_id)
    # pylint: disable=protected-access
    snapshot = TestCase._create_snapshots(audit, [control])[0]
    snapshot_id = snapshot.id
    factories.RelationshipFactory(source=snapshot, destination=audit)

    responses = []
    asmnt_data = {
        "assessment": {
            "_generated": True,
            "audit": {
                "id": self.audit_id,
                "type": "Audit"
            },
            "object": {
                "id": snapshot_id,
                "type": "Snapshot"
            },
            "context": None,
            "title": "New assessment",
        }
    }
    responses.append(self.api.post(all_models.Assessment, asmnt_data))

    asmnt_data["assessment"]["template"] = {
        "id": template_id,
        "type": "AssessmentTemplate"
    }
    responses.append(self.api.post(all_models.Assessment, asmnt_data))
    return responses

  def read(self):
    """Read existing Assessment object."""
    return self.api.get(all_models.Assessment, self.assessment_id)

  def update(self):
    """Update title of existing Assessment object."""
    asmnt = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(asmnt, {"title": factories.random_str()})

  def delete(self):
    """Delete Assessment object."""
    asmnt = all_models.Assessment.query.get(self.assessment_id)
    return self.api.delete(asmnt)

  def read_revisions(self):
    """Read revisions for Assessment object."""
    model_class = get_model("Assessment")
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              model_class,
              query.format("assessment", self.assessment_id)
          )
      )
    return responses

  def map_snapshot(self):
    """Map snapshot to assessment."""
    audit = all_models.Audit.query.get(self.audit_id)
    assessment = all_models.Assessment.query.get(self.assessment_id)
    control = factories.ControlFactory()
    # pylint: disable=protected-access
    snapshot = TestCase._create_snapshots(audit, [control])[0]
    factories.RelationshipFactory(source=snapshot, destination=audit)

    return self.objgen.generate_relationship(
        source=assessment,
        destination=snapshot,
    )[0]

  def deprecate(self):
    """Set status 'Deprecated' for Assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    return self.api.modify_object(assessment, {"status": "Deprecated"})

  def complete(self):
    """Set status 'Completed' for Assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(assessment, {"status": "Completed"})

  def in_progress(self):
    """Set status 'In Progress' for Assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(assessment, {"status": "In Progress"})

  def not_started(self):
    """Set status 'Not Started' for Assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(assessment, {"status": "Not Started"})

  def decline(self):
    """Set status 'Rework Needed' for Assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(assessment, {"status": "Rework Needed"})

  def verify(self):
    """Set status 'Verified' for Assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(assessment, {"status": "Completed", "verified": True})

  def map_comment(self):
    """Map new comment to assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)

    return self.api.put(assessment, {
        "actions": {
            "add_related": [{
                "type": "Comment",
                "description": factories.random_str(),
                "assignee_type": None,
                "context": None,
                "custom_attribute_revision_upd": {
                    "custom_attribute_definition": None,
                    "attributable": {
                        "id": assessment,
                        "type": "Assessment",
                    },
                },
            }]
        }
    })

  def map_document(self):
    """Map new document to assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(assessment, {
        "actions": {
            "add_related": [{
                "id": None,
                "type": "Document",
                "document_type": "EVIDENCE",
                "title": factories.random_str(),
                "link": factories.random_str(),
            }]
        }
    })

  def related_assessments(self):
    """Get related Assessments for existing object."""
    audit = all_models.Audit.query.get(self.audit_id)
    assessment = all_models.Assessment.query.get(self.assessment_id)
    with factories.single_commit():
      control = factories.ControlFactory()
      # pylint: disable=protected-access
      snapshot = TestCase._create_snapshots(audit, [control])[0]
      factories.RelationshipFactory(source=audit, destination=snapshot)
      factories.RelationshipFactory(source=assessment, destination=snapshot)
      assessment2 = factories.AssessmentFactory(
          assessment_type=assessment.assessment_type
      )
      factories.RelationshipFactory(source=assessment2, destination=snapshot)

    return self.api.client.get(
        "/api/related_assessments?object_id={}&object_type=Assessment".format(
            self.assessment_id
        )
    )

  def related_objects(self):
    """Get related objects for existing Assessment."""
    return self.api.client.get(
        "/api/assessments/{}/related_objects".format(self.assessment_id)
    )
