# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration tests for WithLastAssessmentDate logic.

Test cases:

 - Last assessment date on Parent Control
 - Last assessment date on Control Snapshot
 - Index Entries for Parent Controls
 - Index Entries for Snapshots

Changes that trigger updates of dates:

 - Snapshot created (should get date from the original object)
 - Snapshot mapped to assessment
 - Assessment deleted
 - Assessment finished
 - Assessment moved from finished state to any other

Corner cases:

 - Updating dates on snapshots when the original object does not exist

"""

import collections
import datetime
import itertools

import freezegun

from ggrc import models
from ggrc.data_platform import computed_attributes
from ggrc.converters import errors
from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc import generator
from integration.ggrc.models import factories


class TestLastAssessmentDate(TestCase):
  """Integration test suite for WithLastAssessmentDate functionality.

  Setup stage for these tests consists of:
    - 5 controls (Control_0, Control_1, Control_2, Control_3, Control_4)
    - 2 Objectives (Objective_0, Objective_1)
    - 2 audits
      - Audit_0 with snapshots of
        - Control_0, Control_1, Objective_0
      - Audit_1 with snapshots of
        -Control_1, Control_2, Control_3, Objective_0, Objective_1
    - 2 Assessments
      - Assessment_0 on Audit_0 with snapshot mappings for
        - Control_1, Objective_0
      - Assessment_1 on Audit_1 with snapshot mappings for
        - Control_1, Control_2, Objective_0, Objective_1
  """

  def setUp(self):
    super(TestLastAssessmentDate, self).setUp()
    self.api = Api()
    self.generator = generator.ObjectGenerator()
    self.client.get("/login")
    self.init_taskqueue()
    person = models.Person.query.first()
    admin_control = models.AccessControlRole.query.filter_by(
        name="Admin", object_type="Control"
    ).first()
    admin_objective = models.AccessControlRole.query.filter_by(
        name="Admin", object_type="Objective"
    ).first()
    with factories.single_commit():
      controls = [
          factories.ControlFactory(slug="Control_{}".format(i),
                                   title="Control_{}".format(i))
          for i in range(5)
      ]
      objectives = [
          factories.ObjectiveFactory(slug="Objective_{}".format(i),
                                     title="Objective_{}".format(i))
          for i in range(2)
      ]

      for obj in itertools.chain(controls, objectives):
        acr = admin_control if obj.type == "Control" else admin_objective
        factories.AccessControlListFactory(
            object=obj, person=person, ac_role=acr
        )

      audit_0 = factories.AuditFactory(title="Audit_0")
      audit_1 = factories.AuditFactory(title="Audit_1")
      audit_0_snapshots = self._create_snapshots(
          audit_0, controls[:2] + objectives[:1])
      audit_1_snapshots = self._create_snapshots(
          audit_1, controls[1:4] + objectives)
      assessment_0 = factories.AssessmentFactory(
          title="Assessment_0", audit=audit_0)
      assessment_1 = factories.AssessmentFactory(
          title="Assessment_1", audit=audit_1)
      factories.RelationshipFactory(source=assessment_0, destination=audit_0)
      factories.RelationshipFactory(source=audit_1, destination=assessment_1)

      # Audit 0 assessment mappings:
      factories.RelationshipFactory(
          source=assessment_0,
          destination=audit_0_snapshots[1],  # snapshot of control_1
      )
      factories.RelationshipFactory(
          source=assessment_0,
          destination=audit_0_snapshots[2],  # snapshot of objective_0
      )
      # Audit 1 assessment mappings:
      factories.RelationshipFactory(
          source=audit_1_snapshots[0],  # snapshot of control_1
          destination=assessment_1,
      )
      factories.RelationshipFactory(
          source=assessment_1,
          destination=audit_1_snapshots[1],  # snapshot of control_2
      )
      factories.RelationshipFactory(
          source=assessment_1,
          destination=audit_1_snapshots[3],  # snapshot of objective_0
      )
      factories.RelationshipFactory(
          source=audit_1_snapshots[4],  # snapshot of objective_1
          destination=assessment_1,
      )

  def test_no_finished_assessment(self):
    """Test empty last assessment dates."""
    controls = models.Control.query.all()
    for control in controls:
      self.assertEqual(control.last_assessment_date, None)

    snapshots = models.Snapshot.query.all()
    for snapshot in snapshots:
      self.assertEqual(snapshot.last_assessment_date, None)

  def test_single_finished_assessment(self):
    """Test last assessment date for single finished assessment."""
    finish_date = datetime.datetime(2017, 2, 20, 13, 40, 0)
    related_objects = {"Control_1", "Objective_0"}

    with freezegun.freeze_time(finish_date):
      asmt = models.Assessment.query.filter_by(title="Assessment_0").first()
      self.api.put(asmt, {"status": "Completed"})

    for control in models.Control.query.all():
      if control.title in related_objects:
        self.assertEqual(control.last_assessment_date, finish_date)
      else:
        self.assertEqual(control.last_assessment_date, None)

    for snapshot in models.Snapshot.query.all():
      if snapshot.revision.content["title"] in related_objects:
        self.assertEqual(snapshot.last_assessment_date, finish_date)
      else:
        self.assertEqual(snapshot.last_assessment_date, None)

  def test_snapshot_lad_on_new_audits(self):
    """Test snapshot last assessment date for new audits."""

    finish_date = datetime.datetime(2017, 2, 20, 13, 40, 0)
    related_objects = {"Control_1", "Objective_0"}

    with freezegun.freeze_time(finish_date):
      asmt = models.Assessment.query.filter_by(title="Assessment_0").first()
      self.api.put(asmt, {"status": "Completed"})

      program = models.Program.query.first()
      for control in models.Control.query.all():
        factories.RelationshipFactory(source=program, destination=control)

      self.generator.generate_object(models.Audit, data={
          "title": "dummy",
          "program": self.generator.create_stub(program),
          "context": self.generator.create_stub(program.context),
      })

    audit = models.Audit.query.filter_by(title="dummy").first()
    snapshots = models.Snapshot.query.filter(
        models.Snapshot.parent_id == audit.id
    ).all()
    self.assertEqual(len(snapshots), 5)

    for snapshot in snapshots:
      if snapshot.revision.content["title"] in related_objects:
        self.assertEqual(snapshot.last_assessment_date, finish_date)
      else:
        self.assertEqual(snapshot.last_assessment_date, None)

  def test_export_lad_instance(self):
    """Check export Last Assessment Date."""
    finish_date = datetime.datetime(2017, 2, 20, 13, 40, 0)
    finish_date_str = finish_date.strftime("%m/%d/%Y")
    related_objects = {"Control_1", "Objective_0"}

    with freezegun.freeze_time(finish_date):
      asmt = models.Assessment.query.filter_by(title="Assessment_0").first()
      self.api.put(asmt, {"status": "Completed"})

    search_request = [{
        "object_name": "Control",
        "filters": {"expression": {}},
        "fields": ["title", "last_assessment_date"]
    }]
    query = self.export_parsed_csv(search_request)["Control"]

    for control in query:
      if control['Title*'] in related_objects:
        f_date = finish_date_str
      else:
        f_date = ""
      self.assertEqual(control["Last Assessment Date"], f_date)

  def test_export_lad_snapshot(self):
    """Check export Last Assessment Date."""
    finish_date = datetime.datetime(2017, 2, 20, 13, 40, 0)
    finish_date_str = "02/20/2017"
    related_objects = {"*Control_1", "*Control_2"}

    with freezegun.freeze_time(finish_date):
      asmt = models.Assessment.query.filter_by(title="Assessment_1").first()
      self.api.put(asmt, {"status": "Completed"})

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
    }]
    query = self.export_parsed_csv(search_request)["Control Snapshot"]

    for control in query:
      if control['Code'] in related_objects:
        f_date = finish_date_str
      else:
        f_date = ""
      self.assertEqual(control["Last Assessment Date"], f_date)

  def test_import_lad_field(self):
    """Test Last Assessment Date field read only on import."""
    finish_date = datetime.datetime(2017, 2, 20, 13, 40, 0)
    with freezegun.freeze_time(finish_date):
      asmt = models.Assessment.query.filter_by(title="Assessment_0").first()
      self.api.put(asmt, {"status": "Completed"})
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Control"),
        ("code", "Control_1"),
        ("Last Assessment Date", "06/06/2017"),
    ]))
    self._check_csv_response(resp, {
        "Control": {
            "row_warnings": {
                errors.EXPORT_ONLY_WARNING.format(
                    line=3, column_name="Last Assessment Date"
                )
            }
        }
    })

    control = models.Control.query.filter(
        models.Control.slug == "Control_1"
    ).one()
    self.assertEqual(1, len(resp))
    self.assertEqual(1, resp[0]["updated"])
    self.assertEqual(control.last_assessment_date, finish_date)

  def test_handling_rel_revisions(self):
    """Test handling of relationship revisions."""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(
          finished_date=datetime.datetime(2017, 2, 20, 13, 40, 0),
          status="Completed",
      )
      control = factories.ControlFactory()
      snapshots = self._create_snapshots(assessment.audit, [control])
      rel = factories.RelationshipFactory(
          source=assessment,
          destination=snapshots[0]
      )

    rel_revision = models.Revision.query.filter(
        models.Revision.resource_type == rel.type,
        models.Revision.resource_id == rel.id,
    ).first()
    assessment_revision = models.Revision.query.filter(
        models.Revision.resource_type == assessment.type,
        models.Revision.resource_id == assessment.id,
    ).first()

    computed_attributes.compute_attributes([
        rel_revision.id, assessment_revision.id
    ])

    self.assertEqual(
        models.all_models.Attributes.query.count(),
        2,  # One entry for control and one for the control snapshot.
    )
