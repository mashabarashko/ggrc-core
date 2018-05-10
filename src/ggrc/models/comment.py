# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module containing comment model and comment related mixins."""

import itertools

from collections import defaultdict

import sqlalchemy as sa
from sqlalchemy import case
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates
from werkzeug.exceptions import BadRequest

from ggrc import builder
from ggrc import db
from ggrc.models import revision
from ggrc.models import custom_attribute_value
from ggrc.models.deferred import deferred
from ggrc.models.mixins import Base
from ggrc.models.mixins import Described
from ggrc.models.mixins import Notifiable
from ggrc.models.relationship import Relatable, Relationship
from ggrc.access_control.roleable import Roleable
from ggrc.fulltext.mixin import Indexed, ReindexRule
from ggrc.fulltext.attributes import MultipleSubpropertyFullTextAttr
from ggrc.models import inflector
from ggrc.models import reflection
from ggrc.models import utils


class Commentable(object):
  """Mixin for commentable objects.

  This is a mixin for adding default options to objects on which people can
  comment.

  recipients is used for setting who gets notified (Verifer, Requester, ...).
  send_by_default should be used for setting the "send notification" flag in
  the comment modal.

  """
  # pylint: disable=too-few-public-methods

  VALID_RECIPIENTS = frozenset([
      "Assignees",
      "Creators",
      "Verifiers",
      "Admin",
      "Primary Contacts",
      "Secondary Contacts",
  ])

  @validates("recipients")
  def validate_recipients(self, key, value):
    """
      Validate recipients list

      Args:
        value (string): Can be either empty, or
                        list of comma separated `VALID_RECIPIENTS`
    """
    # pylint: disable=unused-argument
    if value:
      value = set(name for name in value.split(",") if name)

    if value and value.issubset(self.VALID_RECIPIENTS):
      # The validator is a bit more smart and also makes some filtering of the
      # given data - this is intended.
      return ",".join(value)
    elif not value:
      return ""
    else:
      raise ValueError(value,
                       'Value should be either empty ' +
                       'or comma separated list of ' +
                       ', '.join(sorted(self.VALID_RECIPIENTS))
                       )

  recipients = db.Column(
      db.String,
      nullable=True,
      default=u"Assignees,Creators,Verifiers")

  send_by_default = db.Column(db.Boolean, nullable=True, default=True)

  _api_attrs = reflection.ApiAttributes("recipients", "send_by_default")

  _aliases = {
      "recipients": "Recipients",
      "send_by_default": "Send by default",
      "comments": {
          "display_name": "Comments",
          "description": 'DELIMITER=";;" double semi-colon separated values',
      },
  }
  _fulltext_attrs = [
      MultipleSubpropertyFullTextAttr("comment", "comments", ["description"]),
  ]

  @classmethod
  def indexed_query(cls):
    return super(Commentable, cls).indexed_query().options(
        orm.Load(cls).subqueryload("comments").load_only("id", "description")
    )

  @classmethod
  def eager_query(cls):
    """Eager Query"""
    query = super(Commentable, cls).eager_query()
    return query.options(orm.subqueryload('comments'))

  @declared_attr
  def comments(cls):  # pylint: disable=no-self-argument
    """Comments related to self via Relationship table."""
    comment_id = case([
        (
            Relationship.destination_type == "Comment",
            Relationship.destination_id
        ),
        (
            Relationship.source_type == "Comment",
            Relationship.source_id
        )
    ])
    commentable_id = case([
        (
            sa.and_(
                Relationship.source_type == cls.__name__,
                Relationship.destination_type == "Comment",
            ),
            Relationship.source_id
        ),
        (
            sa.and_(
                Relationship.source_type == "Comment",
                Relationship.destination_type == cls.__name__,
            ),
            Relationship.destination_id
        ),
    ])

    return db.relationship(
        Comment,
        primaryjoin=lambda: cls.id == commentable_id,
        secondary=Relationship.__table__,
        secondaryjoin=lambda: Comment.id == comment_id,
        viewonly=True,
    )


def reindex_by_relationship(relationship):
  """Reindex comment if relationship changed or created or deleted"""
  if relationship.destination_type == Comment.__name__:
    instance = relationship.source
  elif relationship.source_type == Comment.__name__:
    instance = relationship.destination
  else:
    return []
  if isinstance(instance, (Indexed, Commentable)):
    return [instance]
  return []


class Comment(Roleable, Relatable, Described, Notifiable,
              Base, Indexed, db.Model):
  """Basic comment model."""
  __tablename__ = "comments"

  assignee_type = db.Column(db.String, nullable=False, default=u"")
  revision_id = deferred(db.Column(
      db.Integer,
      db.ForeignKey('revisions.id', ondelete='SET NULL'),
      nullable=True,
  ), 'Comment')
  revision = db.relationship(
      'Revision',
      uselist=False,
  )
  custom_attribute_definition_id = deferred(db.Column(
      db.Integer,
      db.ForeignKey('custom_attribute_definitions.id', ondelete='SET NULL'),
      nullable=True,
  ), 'Comment')
  custom_attribute_definition = db.relationship(
      'CustomAttributeDefinition',
      uselist=False,
  )

  initiator_instance_id = db.Column(db.Integer, nullable=True)
  initiator_instance_type = db.Column(db.String, nullable=True)
  INITIATOR_INSTANCE_TMPL = "{}_comment_initiated_by"

  initiator_instance = utils.PolymorphicRelationship("initiator_instance_id",
                                                     "initiator_instance_type",
                                                     INITIATOR_INSTANCE_TMPL)

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      "assignee_type",
      reflection.Attribute("custom_attribute_revision",
                           create=False,
                           update=False),
      reflection.Attribute("custom_attribute_revision_upd",
                           read=False),
      reflection.Attribute("header_url_link",
                           create=False,
                           update=False),
  )

  _sanitize_html = [
      "description",
  ]

  def get_objects_to_reindex(self):
    """Return list required objects for reindex if comment C.U.D."""
    source_qs = db.session.query(
        Relationship.destination_type, Relationship.destination_id
    ).filter(
        Relationship.source_type == self.__class__.__name__,
        Relationship.source_id == self.id
    )
    destination_qs = db.session.query(
        Relationship.source_type, Relationship.source_id
    ).filter(
        Relationship.destination_type == self.__class__.__name__,
        Relationship.destination_id == self.id
    )
    result_qs = source_qs.union(destination_qs)
    klass_dict = defaultdict(set)
    for klass, object_id in result_qs:
      klass_dict[klass].add(object_id)

    queries = []
    for klass, object_ids in klass_dict.iteritems():
      model = inflector.get_model(klass)
      if not model:
        continue
      if issubclass(model, (Indexed, Commentable)):
        queries.append(model.query.filter(model.id.in_(list(object_ids))))
    return list(itertools.chain(*queries))

  AUTO_REINDEX_RULES = [
      ReindexRule("Comment", lambda x: x.get_objects_to_reindex()),
      ReindexRule("Relationship", reindex_by_relationship),
  ]

  @builder.simple_property
  def header_url_link(self):
    """Return header url link to comment if that comment related to proposal
    and that proposal is only proposed."""
    if self.initiator_instance_type != "Proposal":
      return ""
    proposed_status = self.initiator_instance.STATES.PROPOSED
    if self.initiator_instance.status == proposed_status:
      return "proposal_link"
    return ""

  @classmethod
  def eager_query(cls):
    query = super(Comment, cls).eager_query()
    return query.options(
        orm.joinedload('revision'),
        orm.joinedload('custom_attribute_definition')
           .undefer_group('CustomAttributeDefinition_complete'),
    )

  @builder.simple_property
  def custom_attribute_revision(self):
    """Get the historical value of the relevant CA value."""
    if not self.revision:
      return None
    revision = self.revision.content
    cav_stored_value = revision['attribute_value']
    cad = self.custom_attribute_definition
    return {
        'custom_attribute': {
            'id': cad.id if cad else None,
            'title': cad.title if cad else 'DELETED DEFINITION',
        },
        'custom_attribute_stored_value': cav_stored_value,
    }

  def custom_attribute_revision_upd(self, value):
    """Create a Comment-CA mapping with current CA value stored."""
    ca_revision_dict = value.get('custom_attribute_revision_upd')
    if not ca_revision_dict:
      return
    cad_id, parent_type, parent_id = self._get_ca_value(ca_revision_dict)

    rev, cav = revision.Revision, custom_attribute_value.CustomAttributeValue

    self.revision_id = db.session.query(
        rev.id,
    ).join(
        cav,
        sa.and_(
            rev.resource_type == cav.__name__,
            rev.resource_id == cav.id,
        ),
    ).filter(
        cav.custom_attribute_id == cad_id,
        cav.attributable_type == parent_type,
        cav.attributable_id == parent_id,
    ).order_by(
        rev.id.desc(),
    ).limit(1).scalar()

    if not self.revision_id:
      raise BadRequest("No Revision found for CA value for CAD.id {} for {} "
                       "with id {}"
                       .format(cad_id, parent_type, parent_id))

    self.custom_attribute_definition_id = cad_id

  @staticmethod
  def _get_ca_value(ca_revision_dict):
    """Get data to identify a CAV from json and do a basic validation.

    Returns: a tuple of CAD.id, CAV.attributable_type, CAV.attributable_id
    """
    try:
      cad_id = ca_revision_dict["custom_attribute_definition"]["id"]
      assert cad_id is not None
    except (KeyError, AssertionError):
      raise ValueError("CA definition id expected under "
                       "'custom_attribute_definition.id': {}"
                       .format(ca_revision_dict))

    try:
      parent_stub = ca_revision_dict["attributable"]
      parent_id, parent_type = parent_stub["id"], parent_stub["type"]
      assert None not in {parent_id, parent_type}
    except (KeyError, AssertionError):
      raise ValueError("Attributable stub expected under 'attributable': {}"
                       .format(ca_revision_dict))
    return cad_id, parent_type, parent_id


class CommentInitiator(object):  # pylint: disable=too-few-public-methods

  @sa.ext.declarative.declared_attr
  def initiator_comments(cls):  # pylint: disable=no-self-argument
    """Relationship.

    Links comments to object that are the reason of that comment generation."""

    def join_function():
      return sa.and_(
          sa.orm.foreign(Comment.initiator_instance_type) == cls.__name__,
          sa.orm.foreign(Comment.initiator_instance_id) == cls.id,
      )

    return sa.orm.relationship(
        Comment,
        primaryjoin=join_function,
        backref=Comment.INITIATOR_INSTANCE_TMPL.format(cls.__name__),
    )
