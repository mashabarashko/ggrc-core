# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for AutoStatusChangeable mixin"""

import ddt

from ggrc import models
from ggrc.access_control.role import get_custom_roles_for
from integration.ggrc import generator
from integration.ggrc.access_control import acl_helper
from integration.ggrc.models import factories
from integration.ggrc.models import test_assessment


class TestMixinAutoStatusChangeableBase(test_assessment.TestAssessmentBase):
  """Base Test case for AutoStatusChangeable mixin"""

  def setUp(self):
    super(TestMixinAutoStatusChangeableBase, self).setUp()
    self.client.get("/login")
    self.objgen = generator.ObjectGenerator()

  def create_assignees_restful(self, obj, persons):
    """Add assignees via RESTful API instead of directly via backend.

    Used for addind assignees after object has already been created.

    Args:
      obj: Assignable object.
      persons: [("(string) email", "Assignee roles"), ...] A list of people
        and their roles
    Returns:
      List of relationship.
    """

    relationships = []
    for person, roles in persons:
      person = factories.PersonFactory(email=person)

      attrs = {
          "AssigneeType": roles,
      }
      response, relationship = self.objgen.generate_relationship(
          person, obj, context=obj.context, attrs=attrs)
      self.assertEqual(response.status_code, 201)

      relationships += [relationship]
    return relationships

  def modify_assignee(self, obj, email, new_roles):
    """Modfiy assignee type.

    Args:
      obj: Object
      email: Person's email
      new_role: New roles for AssigneeType
    """
    person = models.Person.query.filter_by(email=email).first()
    ac_roles = {
        acr_name: acr_id
        for acr_id, acr_name in get_custom_roles_for(obj.type).items()
    }
    self.api.modify_object(obj, {
        "access_control_list": [
            acl_helper.get_acl_json(ac_roles[role], person.id)
            for role in new_roles
        ]
    })

  def delete_assignee(self, obj, email):
    """Deletes user-object relationship user when no more assignee roles.

    This operation is equal to deleting user from a role when that is his only
    role left on the object.

    Args:
      obj: object
      email: assignee's email
    """
    self.modify_assignee(obj, email, [])

  def create_assessment(self, people=None):
    """Create default assessment with some default assignees in all roles.
    Args:
      people: List of tuples with email address and their assignee roles for
              Assessments.
    Returns:
      Assessment object.
    """
    assessment = factories.AssessmentFactory()
    context = factories.ContextFactory(related_object=assessment)
    assessment.context = context

    if not people:
      people = [
          ("creator@example.com", "Creators"),
          ("assessor_1@example.com", "Assignees"),
          ("assessor_2@example.com", "Assignees"),
          ("verifier_1@example.com", "Verifiers"),
          ("verifier_2@example.com", "Verifiers"),
      ]

    defined_assessors = len([1 for _, role in people
                             if "Assignees" in role])
    defined_creators = len([1 for _, role in people
                            if "Creators" in role])
    defined_verifiers = len([1 for _, role in people
                             if "Verifiers" in role])

    assignee_roles = self.create_assignees(assessment, people)

    creators = [assignee for assignee, roles in assignee_roles
                if "Creators" in roles]
    assignees = [assignee for assignee, roles in assignee_roles
                 if "Assignees" in roles]
    verifiers = [assignee for assignee, roles in assignee_roles
                 if "Verifiers" in roles]

    self.assertEqual(len(creators), defined_creators)
    self.assertEqual(len(assignees), defined_assessors)
    self.assertEqual(len(verifiers), defined_verifiers)
    return assessment

  def change_status(self, obj, status,
                    expected_status=None, check_verified=False):
    """Change status of an object."""
    self.api.modify_object(obj, {
        "status": status
    })
    obj = self.refresh_object(obj)
    if expected_status:
      self.assertEqual(obj.status, expected_status)
    else:
      self.assertEqual(obj.status, status)

    if check_verified:
      self.assertEqual(obj.verified, True)
    return obj

  def create_simple_assessment(self):
    """Create simple assessment with some assignees and in FINAL state."""
    people = [
        ("creator@example.com", "Creators"),
        ("assessor_1@example.com", "Assignees"),
        ("assessor_2@example.com", "Assignees"),
    ]

    assessment = self.create_assessment(people)
    assessment = self.refresh_object(assessment)

    self.api.modify_object(assessment, {
        "title": assessment.title + " modified, change #1"
    })

    assessment = self.refresh_object(assessment)

    assessment = self.change_status(assessment, assessment.FINAL_STATE)

    assessment = self.refresh_object(assessment)

    self.assertEqual(assessment.status, models.Assessment.FINAL_STATE)
    return assessment


@ddt.ddt
class TestFirstClassAttributes(TestMixinAutoStatusChangeableBase):
  """Test case for AutoStatusChangeable first class attributes handlers"""
  # pylint: disable=invalid-name

  @ddt.data(models.Assessment.DONE_STATE,
            models.Assessment.FINAL_STATE,
            models.Assessment.PROGRESS_STATE,
            models.Assessment.REWORK_NEEDED
            )
  def test_update_label_not_change_status(self, from_status):
    """Assessment in '{0}' NOT changed when adding label."""
    # This test should fail when new Label implementation will be merged
    assessment = factories.AssessmentFactory(status=from_status)
    self.api.modify_object(assessment, {
        'label': 'Followup'
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(from_status, assessment.status)

  @ddt.data(
      ('title', 'new title', models.Assessment.DONE_STATE,),
      ('title', 'new title', models.Assessment.FINAL_STATE),
      ('test_plan', 'test_plan v2', models.Assessment.DONE_STATE),
      ('test_plan', 'test_plan v2', models.Assessment.FINAL_STATE),
      ('notes', 'new note', models.Assessment.DONE_STATE),
      ('notes', 'new note', models.Assessment.FINAL_STATE),
      ('description', 'some description', models.Assessment.DONE_STATE),
      ('description', 'some description', models.Assessment.FINAL_STATE),
      ('slug', 'some code', models.Assessment.DONE_STATE),
      ('slug', 'some code', models.Assessment.FINAL_STATE),
      ('start_date', '2020-01-01', models.Assessment.DONE_STATE),
      ('start_date', '2020-01-01', models.Assessment.FINAL_STATE),
      ('design', 'Effective', models.Assessment.DONE_STATE),
      ('design', 'Effective', models.Assessment.FINAL_STATE),
      ('operationally', 'Effective', models.Assessment.DONE_STATE),
      ('operationally', 'Effective', models.Assessment.FINAL_STATE),
      ('assessment_type', 'Risk', models.Assessment.DONE_STATE),
      ('assessment_type', 'Risk', models.Assessment.FINAL_STATE),
  )
  @ddt.unpack
  def test_update_field_change_status(self, field_name, new_value,
                                      from_status):
    """Move Assessment from '{2}' to 'In Progress' when field '{0}' updated"""
    assessment = factories.AssessmentFactory(status=from_status)
    expected_status = models.Assessment.PROGRESS_STATE

    self.api.modify_object(assessment, {
        field_name: new_value
    })
    assessment = self.refresh_object(assessment)

    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('title', 'new title', models.Assessment.START_STATE),
      ('title', 'new title', models.Assessment.REWORK_NEEDED),
      ('test_plan', 'test_plan v2', models.Assessment.START_STATE),
      ('test_plan', 'test_plan v2', models.Assessment.REWORK_NEEDED),
      ('notes', 'new note', models.Assessment.START_STATE),
      ('notes', 'new note', models.Assessment.REWORK_NEEDED),
      ('description', 'some description', models.Assessment.START_STATE),
      ('description', 'some description', models.Assessment.REWORK_NEEDED),
      ('slug', 'some code', models.Assessment.START_STATE),
      ('slug', 'some code', models.Assessment.REWORK_NEEDED),
      ('start_date', '2020-01-01', models.Assessment.START_STATE),
      ('start_date', '2020-01-01', models.Assessment.REWORK_NEEDED),
      ('design', 'Effective', models.Assessment.START_STATE),
      ('design', 'Effective', models.Assessment.REWORK_NEEDED),
      ('operationally', 'Effective', models.Assessment.START_STATE),
      ('operationally', 'Effective', models.Assessment.REWORK_NEEDED),
      ('assessment_type', 'Risk', models.Assessment.START_STATE),
      ('assessment_type', 'Risk', models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_update_field_not_change_status(self, field_name, new_value,
                                          from_status):
    """Assessment in '{2}' NOT changed when field '{0}' updated"""
    assessment = factories.AssessmentFactory(status=from_status)
    self.api.modify_object(assessment, {
        field_name: new_value
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(from_status, assessment.status)


@ddt.ddt
class TestSnapshots(TestMixinAutoStatusChangeableBase):
  """Test case for AutoStatusChangeable mapping/unmapping snapshots handlers"""
  # pylint: disable=invalid-name

  @ddt.data(
      (models.Assessment.DONE_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.FINAL_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.START_STATE, models.Assessment.START_STATE),
      (models.Assessment.REWORK_NEEDED, models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_mapping_snapshot_type_status_check(self, from_status,
                                              expected_status):
    """Move Assessment form '{0}' to '{1}' when map snapshot.

    Snapshot type = assessment type
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit, status=from_status)
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory(title='test control')
    snapshot = self._create_snapshots(audit, [control])[0]

    response, _ = self.objgen.generate_relationship(
        source=assessment,
        destination=snapshot,
        context=None,
    )
    assessment = self.refresh_object(assessment)
    self.assertStatus(response, 201)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      (models.Assessment.DONE_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.FINAL_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.START_STATE, models.Assessment.START_STATE),
      (models.Assessment.REWORK_NEEDED, models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_unmapping_snapshot_status_check(self, from_status, expected_status):
    """Move Assessment from '{0}' from '{1}' when un map snapshot.

        Snapshot type = assessment type
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory(title='test control')

    assessment_id = assessment.id
    snapshot = self._create_snapshots(audit, [control])[0]

    response, relationship = self.objgen.generate_relationship(
        source=assessment,
        destination=snapshot,
        context=None,
    )
    assessment = self.refresh_object(assessment, assessment_id)
    assessment = self.change_status(assessment, from_status)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertEqual(from_status, assessment.status)
    response = self.api.delete(relationship)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertStatus(response, 200)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      (models.Assessment.DONE_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.FINAL_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.START_STATE, models.Assessment.START_STATE),
      (models.Assessment.REWORK_NEEDED, models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_mapping_snapshot_not_assessment_type(self, from_status,
                                                expected_status):
    """Move Assessment form '{0}' to '{1}' when map snapshot.

    Snapshot type != assessment type
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit,
                                               status=from_status,
                                               assessment_type='Contract')
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory(title='test control')

    snapshot = self._create_snapshots(audit, [control])[0]

    response, _ = self.objgen.generate_relationship(
        source=assessment,
        destination=snapshot,
        context=None,
    )
    assessment = self.refresh_object(assessment)
    self.assertStatus(response, 201)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      (models.Assessment.DONE_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.FINAL_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.START_STATE, models.Assessment.START_STATE),
      (models.Assessment.REWORK_NEEDED, models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_unmapping_snapshot_not_assessment_type(self, from_status,
                                                  expected_status):
    """Move Assessment from '{0}' from '{1}' when un map snapshot.

        Snapshot type != assessment type
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit,
                                               assessment_type='Contract')
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory(title='test control')
    assessment_id = assessment.id
    snapshot = self._create_snapshots(audit, [control])[0]
    response, relationship = self.objgen.generate_relationship(
        source=assessment,
        destination=snapshot,
        context=None,
    )
    assessment = self.refresh_object(assessment)
    assessment = self.change_status(assessment, from_status)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertEqual(from_status, assessment.status)
    response = self.api.delete(relationship)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertStatus(response, 200)
    self.assertEqual(expected_status, assessment.status)


@ddt.ddt
class TestDocuments(TestMixinAutoStatusChangeableBase):
  """Test case for AutoStatusChangeable documents handlers"""
  # pylint: disable=invalid-name

  @ddt.data(
      ('REFERENCE_URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('REFERENCE_URL', models.Assessment.START_STATE,
       models.Assessment.START_STATE),
      ('EVIDENCE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('EVIDENCE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
  )
  @ddt.unpack
  def test_document_added_status_check(self, document_type,
                                       from_status, expected_status):
    """Move Assessment from '{1}' to '{2}' adding document of type {0}"""
    assessment = factories.AssessmentFactory(status=from_status)
    related_document = {
        'id': None,
        'type': 'Document',
        'document_type': document_type,
        'title': 'google.com',
        'link': 'google.com',
    }
    response = self.api.put(assessment, {
        'actions': {
            'add_related': [related_document]
        }
    })
    assessment = self.refresh_object(assessment)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('REFERENCE_URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('REFERENCE_URL', models.Assessment.START_STATE,
       models.Assessment.START_STATE),
      ('EVIDENCE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('EVIDENCE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
  )
  @ddt.unpack
  def test_document_remove_related(self, document_type,
                                   from_status, expected_status):
    """Move Assessment from '{1}' to '{2}' remove document of type {0}"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      document = factories.DocumentFactory(document_type=document_type,
                                           title='google.com',
                                           link='google.com')
      factories.RelationshipFactory(destination=assessment, source=document)

    response = self.api.put(assessment, {
        'actions': {
            'remove_related': [{
                'id': document.id,
                'type': 'Document',
            }]
        }
    })
    assessment = self.refresh_object(assessment)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('REFERENCE_URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('REFERENCE_URL', models.Assessment.START_STATE,
       models.Assessment.START_STATE),
      ('EVIDENCE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('EVIDENCE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
  )
  @ddt.unpack
  def test_document_delete(self, document_type, from_status,
                           expected_status):
    """Move Assessment from '{1}' to '{2}' delete document of type {0}"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      document = factories.DocumentFactory(document_type=document_type,
                                           title='google.com',
                                           link='google.com')
      factories.RelationshipFactory(destination=assessment, source=document)
    assessment_id = assessment.id
    response = self.api.delete(document)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      ('REFERENCE_URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('REFERENCE_URL', models.Assessment.START_STATE,
       models.Assessment.START_STATE),
      ('EVIDENCE', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('EVIDENCE', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.DONE_STATE,
       models.Assessment.PROGRESS_STATE),
      ('URL', models.Assessment.START_STATE,
       models.Assessment.PROGRESS_STATE),
  )
  @ddt.unpack
  def test_document_update_status_check(self, document_type, from_status,
                                        expected_status):
    """Move Assessment from '{1}' to '{2}' update document of type {0}"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      document = factories.DocumentFactory(document_type=document_type,
                                           title='google.com',
                                           link='google.com')
      factories.RelationshipFactory(destination=assessment, source=document)
    assessment_id = assessment.id
    response = self.api.modify_object(document, {
        'title': 'New document',
        'link': 'New document',
    })
    assessment = self.refresh_object(assessment, assessment_id)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)


@ddt.ddt
class TestCustomAttributes(TestMixinAutoStatusChangeableBase):
  """Test case for AutoStatusChangeable custom attributes handlers"""
  # pylint: disable=invalid-name

  @ddt.data(models.Assessment.DONE_STATE,
            models.Assessment.FINAL_STATE,
            models.Assessment.PROGRESS_STATE,
            models.Assessment.REWORK_NEEDED
            )
  def test_global_ca_admin_add_not_change_status(self, from_status):
    """Assessment in '{0}' NOT changed when adding 'global custom attribute'"""
    with factories.single_commit():
      assessment = factories.AssessmentFactory(status=from_status)
      factories.CustomAttributeDefinitionFactory(definition_type='assessment',
                                                 attribute_type='Rich Text',
                                                 title='rich_test_gca',
                                                 multi_choice_options=''
                                                 )
    assessment = self.refresh_object(assessment)
    self.assertEqual(from_status, assessment.status)

  @ddt.data(
      (models.Assessment.DONE_STATE, ''),
      (models.Assessment.DONE_STATE, None),
      (models.Assessment.FINAL_STATE, ''),
      (models.Assessment.FINAL_STATE, None),
      (models.Assessment.PROGRESS_STATE, ''),
      (models.Assessment.PROGRESS_STATE, None),
      (models.Assessment.REWORK_NEEDED, ''),
      (models.Assessment.REWORK_NEEDED, None),
  )
  @ddt.unpack
  def test_global_ca_update_empty_value_not_change_status(self, from_status,
                                                          value):
    """Assessment in '{0}' NOT changed when adding GCA with '{1}' value

    Our frontend generates CAVs with attribute_value='' for each missing
    CAV object in custom_attribute_values. And transition from CAV is None to
    CAV.attribute_value == '' shouldn't trigger status change, since both mean
    that the CAV is not filled in.
    """
    with factories.single_commit():
      ca_factory = factories.CustomAttributeDefinitionFactory
      gca = ca_factory(definition_type='assessment',
                       title='rich_test_gca',
                       attribute_type='Rich Text'
                       )
      assessment = factories.AssessmentFactory(status=from_status)
    self.api.modify_object(assessment, {
        'custom_attribute_values': [{
            'custom_attribute_id': gca.id,
            'attribute_value': value,
        }],
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(from_status, assessment.status)

  @ddt.data(
      (models.Assessment.DONE_STATE, ''),
      (models.Assessment.DONE_STATE, None),
      (models.Assessment.FINAL_STATE, ''),
      (models.Assessment.FINAL_STATE, None),
      (models.Assessment.PROGRESS_STATE, ''),
      (models.Assessment.PROGRESS_STATE, None),
      (models.Assessment.REWORK_NEEDED, ''),
      (models.Assessment.REWORK_NEEDED, None),
  )
  @ddt.unpack
  def test_gca_update_empty_value_and_status_not_change_status(self,
                                                               from_status,
                                                               value):
    """Assessment in '{0}' NOT changed when add GCA with '{1}' value + status

    Same as above + update status in the same PUT
    """
    with factories.single_commit():
      ca_factory = factories.CustomAttributeDefinitionFactory
      gca = ca_factory(definition_type='assessment',
                       title='rich_test_gca',
                       attribute_type='Rich Text'
                       )
      assessment = factories.AssessmentFactory()
    self.api.modify_object(assessment, {
        'custom_attribute_values': [{
            'custom_attribute_id': gca.id,
            'attribute_value': value,
        }],
        'status': from_status
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(from_status, assessment.status)

  @ddt.data(
      (models.Assessment.DONE_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.FINAL_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.START_STATE, models.Assessment.START_STATE),
      (models.Assessment.REWORK_NEEDED, models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_global_ca_update_change_status(self, from_status, expected_status):
    """Move Assessment from '{0}' to '{1}' update 'global custom attribute'"""
    with factories.single_commit():
      ca_factory = factories.CustomAttributeDefinitionFactory
      gca = ca_factory(definition_type='assessment',
                       title='rich_test_gca',
                       attribute_type='Rich Text',
                       multi_choice_options=''
                       )
      assessment = factories.AssessmentFactory(status=from_status)
    self.api.modify_object(assessment, {
        'custom_attribute_values': [{
            'custom_attribute_id': gca.id,
            'attribute_value': 'new value',
        }]
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(
      (models.Assessment.DONE_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.FINAL_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.START_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.REWORK_NEEDED, models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_local_ca_update_change_status(self, from_status, expected_status):
    """Move Assessment from '{0}' to '{1}' update 'local custom attribute'"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit, status=from_status)
      factories.RelationshipFactory(source=audit, destination=assessment)

      cad = factories.CustomAttributeDefinitionFactory(
          definition_id=assessment.id,
          definition_type='assessment',
          attribute_type='Rich Text',
          title='rich_test_gca',
          multi_choice_options='',
      )
    self.api.modify_object(assessment, {
        'custom_attribute_values': [{
            'custom_attribute_id': cad.id,
            'attribute_value': 'new value',
        }]
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(expected_status, assessment.status)


@ddt.ddt
class TestOther(TestMixinAutoStatusChangeableBase):
  """Test case for AutoStatusChangeable. Comment, custom access role,
   map/unmap issue, assignees Handlers"""
  # pylint: disable=invalid-name

  @ddt.data(
      (models.Assessment.DONE_STATE, models.Assessment.DONE_STATE),
      (models.Assessment.FINAL_STATE, models.Assessment.FINAL_STATE),
      (models.Assessment.START_STATE, models.Assessment.PROGRESS_STATE),
      (models.Assessment.REWORK_NEEDED, models.Assessment.REWORK_NEEDED),
  )
  @ddt.unpack
  def test_add_comment_status_check(self, from_status, expected_status):
    """Move Assessment from '{0}' to '{1}' when comment is added."""
    assessment = factories.AssessmentFactory(status=from_status)
    response = self.api.put(assessment, {
        'actions': {
            'add_related': [{
                "type": "Comment",
                "description": "comment",
                "assignee_type": None,
                "context": None,
                "custom_attribute_revision_upd": None,
            }]
        }
    })
    assessment = self.refresh_object(assessment)
    self.assert200(response)
    self.assertEqual(expected_status, assessment.status)

  @ddt.data(models.Assessment.DONE_STATE,
            models.Assessment.FINAL_STATE,
            models.Assessment.PROGRESS_STATE,
            models.Assessment.REWORK_NEEDED
            )
  def test_custom_access_role_add_not_change_status(self, from_status):
    """Assessment in '{0}' NOT changed when adding custom access role."""
    assessment = factories.AssessmentFactory(status=from_status)
    factories.AccessControlRoleFactory(
        name='Test assessment role',
        object_type='Assessment',
    )
    assessment = self.refresh_object(assessment)
    self.assertEqual(from_status, assessment.status)

  @ddt.data(models.Assessment.DONE_STATE,
            models.Assessment.FINAL_STATE,
            models.Assessment.PROGRESS_STATE,
            models.Assessment.REWORK_NEEDED
            )
  def test_mapping_issue_not_change_status(self, from_status):
    """Assessment '{0}' NOT changed when Map Issue."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit,
                                               status=from_status,
                                               assessment_type='Contract')
      factories.RelationshipFactory(source=audit, destination=assessment)
      issue = factories.IssueFactory(title='test Issue')

    response, _ = self.objgen.generate_relationship(
        source=assessment,
        destination=issue,
        context=None,
    )
    assessment = self.refresh_object(assessment)
    self.assertStatus(response, 201)
    self.assertEqual(from_status, assessment.status)

  @ddt.data(models.Assessment.DONE_STATE,
            models.Assessment.FINAL_STATE,
            models.Assessment.PROGRESS_STATE,
            models.Assessment.REWORK_NEEDED
            )
  def test_unmapping_issue_not_change_status(self, from_status):
    """Assessment '{0}' NOT changed when un map Issue."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
      issue = factories.IssueFactory(title='test Issue')
    assessment_id = assessment.id
    response, relationship = self.objgen.generate_relationship(
        source=assessment,
        destination=issue,
        context=None,
    )
    assessment = self.refresh_object(assessment, assessment_id)
    assessment = self.change_status(assessment, from_status)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertEqual(from_status, assessment.status)
    response = self.api.delete(relationship)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertStatus(response, 200)
    self.assertEqual(from_status, assessment.status)

  @ddt.data(models.Assessment.DONE_STATE,
            models.Assessment.FINAL_STATE,
            models.Assessment.PROGRESS_STATE,
            models.Assessment.REWORK_NEEDED
            )
  def test_delete_issue_not_change_status(self, from_status):
    """Assessment '{0}' NOT changed when delete Issue."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)
      issue = factories.IssueFactory(title='test Issue')
    assessment_id = assessment.id
    self.objgen.generate_relationship(
        source=assessment,
        destination=issue,
        context=None,
    )
    assessment = self.refresh_object(assessment, assessment_id)
    assessment = self.change_status(assessment, from_status)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertEqual(from_status, assessment.status)
    response = self.api.delete(issue)
    assessment = self.refresh_object(assessment, assessment_id)
    self.assertStatus(response, 200)
    self.assertEqual(from_status, assessment.status)

  @ddt.data("DONE_STATE", "START_STATE")
  def test_changing_assignees_should_not_change_status(self, test_state):
    """Adding/changing/removing assignees shouldn't change status

    Test assessment in FINAL_STATE should not get to PROGRESS_STATE on
    assignee edit.
    """
    people = [
        ("creator@example.com", "Creators"),
        ("assessor_1@example.com", "Assignees"),
        ("assessor_2@example.com", "Assignees"),
    ]

    assessment = self.create_assessment(people)
    assessment = self.refresh_object(assessment)
    assessment = self.change_status(assessment,
                                    getattr(assessment, test_state))
    self.assertEqual(assessment.status,
                     getattr(models.Assessment, test_state))
    self.modify_assignee(assessment,
                         "creator@example.com",
                         ["Creators", "Assignees"])
    assessment = self.refresh_object(assessment)
    self.assertEqual(assessment.status,
                     getattr(models.Assessment, test_state))
    new_assessors = [("assessor_3_added_later@example.com", "Verifiers")]
    self.create_assignees_restful(assessment, new_assessors)
    assessment = self.refresh_object(assessment)
    self.assertEqual(assessment.status,
                     getattr(models.Assessment, test_state))
    self.delete_assignee(assessment, "assessor_1@example.com")
    assessment = self.refresh_object(assessment)
    self.assertEqual(assessment.status,
                     getattr(models.Assessment, test_state))

  def test_assessment_verifiers_full_cycle_first_class_edit(self):
    """Test models.Assessment with verifiers full flow

    Test moving from START_STATE to PROGRESS_STATE to FINAL_STATE and back to
    PROGRESS_STATE on edit.
    """
    assessment = self.create_assessment()

    self.assertEqual(assessment.status,
                     models.Assessment.START_STATE)

    assessment = self.refresh_object(assessment)

    self.api.modify_object(assessment, {
        "title": assessment.title + " modified, change #1"
    })

    assessment = self.refresh_object(assessment)

    assessment = self.change_status(assessment, assessment.DONE_STATE)

    self.assertEqual(assessment.title.endswith("modified, change #1"),
                     True)

    self.assertEqual(assessment.status,
                     models.Assessment.DONE_STATE)

    self.api.modify_object(assessment, {
        "title": assessment.title + " modified, change #2"
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(assessment.title.endswith("modified, change #2"),
                     True)
    self.assertEqual(assessment.status,
                     models.Assessment.PROGRESS_STATE)

    assessment = self.change_status(assessment,
                                    assessment.VERIFIED_STATE,
                                    assessment.FINAL_STATE)

    self.assertEqual(assessment.status, assessment.FINAL_STATE)
    self.assertEqual(assessment.verified, True)

    self.api.modify_object(assessment, {
        "title": assessment.title + "modified, change #3"
    })
    assessment = self.refresh_object(assessment)
    self.assertEqual(assessment.title.endswith("modified, change #3"),
                     True)
    self.assertEqual(assessment.status,
                     models.Assessment.PROGRESS_STATE)

  def test_modifying_person_custom_attribute_changes_status(self):
    """Test that changing a Person CA changes the status to in progress."""
    person_id = models.Person.query.first().id
    _, another_person = self.objgen.generate_person()

    # define a Custom Attribute of type Person...
    _, ca_def = self.objgen.generate_custom_attribute(
        definition_type="assessment",
        attribute_type="Map:Person",
        title="best employee")

    # create assessment with a Person Custom Attribute set, make sure the
    # state is set to final
    assessment = self.create_simple_assessment()

    custom_attribute_values = [{
        "custom_attribute_id": ca_def.id,
        "attribute_value": "Person:" + str(person_id),
    }]
    self.api.modify_object(assessment, {
        "custom_attribute_values": custom_attribute_values
    })

    assessment = self.change_status(assessment, assessment.FINAL_STATE)
    assessment = self.refresh_object(assessment)

    # now change the Person CA and check what happens with the status
    custom_attribute_values = [{
        "custom_attribute_id": ca_def.id,
        "attribute_value": "Person:" + str(another_person.id),  # make a change
    }]
    self.api.modify_object(assessment, {
        "custom_attribute_values": custom_attribute_values
    })

    assessment = self.refresh_object(assessment)
    self.assertEqual(assessment.status, models.Assessment.PROGRESS_STATE)

    # perform the same test for the "in review" state
    assessment = self.change_status(assessment, assessment.DONE_STATE)
    assessment = self.refresh_object(assessment)

    custom_attribute_values = [{
        "custom_attribute_id": ca_def.id,
        "attribute_value": "Person:" + str(person_id),  # make a change
    }]
    self.api.modify_object(assessment, {
        "custom_attribute_values": custom_attribute_values
    })

    assessment = self.refresh_object(assessment)
    self.assertEqual(assessment.status, models.Assessment.PROGRESS_STATE)

  def test_asmt_with_mandatory_lca_to_deprecated_state(self):
    """Test new Assessment with not filled mandatory LCA could be Deprecated"""
    # pylint: disable=attribute-defined-outside-init
    with factories.single_commit():
      self.audit = factories.AuditFactory()
      self.control = factories.ControlFactory(test_plan="Control Test Plan")
      self.snapshot = self._create_snapshots(self.audit, [self.control])[0]

      template = factories.AssessmentTemplateFactory(
          test_plan_procedure=False,
          procedure_description="Assessment Template Test Plan"
      )
      custom_attribute_definition = {
          "definition_type": "assessment_template",
          "definition_id": template.id,
          "title": "test checkbox",
          "attribute_type": "Checkbox",
          "multi_choice_options": "test checkbox label",
          "mandatory": True,
      }
      factories.CustomAttributeDefinitionFactory(**custom_attribute_definition)

    response = self.assessment_post(template)

    self.assertEqual(response.json["assessment"]["status"],
                     models.Assessment.START_STATE)
    asmt = models.Assessment.query.get(response.json["assessment"]["id"])
    asmt = self.change_status(asmt, models.Assessment.DEPRECATED)
    asmt = self.refresh_object(asmt)
    self.assertEqual(asmt.status, models.Assessment.DEPRECATED)
