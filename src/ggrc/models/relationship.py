# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for Relationship model and related classes."""

import collections
import sqlalchemy as sa
from sqlalchemy import or_, and_
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates

from ggrc import db
from ggrc.login import is_external_app_user
from ggrc.models.mixins import Base
from ggrc.models import reflection
from ggrc.models.exceptions import ValidationError


class Relationship(Base, db.Model):
  """Relationship model."""
  __tablename__ = 'relationships'
  source_id = db.Column(db.Integer, nullable=False)
  source_type = db.Column(db.String, nullable=False)
  destination_id = db.Column(db.Integer, nullable=False)
  destination_type = db.Column(db.String, nullable=False)
  parent_id = db.Column(
      db.Integer,
      db.ForeignKey('relationships.id', ondelete='SET NULL'),
      nullable=True,
  )
  parent = db.relationship(
      lambda: Relationship,
      remote_side=lambda: Relationship.id
  )
  automapping_id = db.Column(
      db.Integer,
      db.ForeignKey('automappings.id', ondelete='CASCADE'),
      nullable=True,
  )
  is_external = db.Column(db.Boolean, nullable=False, default=False)

  def get_related_for(self, object_type):
    """Return related object for sent type."""
    if object_type == self.source_type:
      return self.destination
    if object_type == self.destination_type:
      return self.source

  @property
  def source_attr(self):
    return '{0}_source'.format(self.source_type)

  @property
  def source(self):
    return getattr(self, self.source_attr)

  @source.setter
  def source(self, value):
    self.source_id = getattr(value, 'id', None)
    self.source_type = getattr(value, 'type', None)
    self.validate_relatable_type("source", value)
    return setattr(self, self.source_attr, value)

  @property
  def destination_attr(self):
    return '{0}_destination'.format(self.destination_type)

  @property
  def destination(self):
    return getattr(self, self.destination_attr)

  @destination.setter
  def destination(self, value):
    self.destination_id = getattr(value, 'id', None)
    self.destination_type = getattr(value, 'type', None)
    self.validate_relatable_type("destination", value)
    return setattr(self, self.destination_attr, value)

  @classmethod
  def find_related(cls, object1, object2):
    return cls.get_related_query(object1, object2).first()

  @classmethod
  def get_related_query(cls, object1, object2):
    def predicate(src, dst):
      return and_(
          Relationship.source_type == src.type,
          or_(Relationship.source_id == src.id, src.id == None),  # noqa
          Relationship.destination_type == dst.type,
          or_(Relationship.destination_id == dst.id, dst.id == None),  # noqa
      )
    return Relationship.query.filter(
        or_(predicate(object1, object2), predicate(object2, object1))
    )

  @staticmethod
  def _extra_table_args(cls):
    return (
        db.UniqueConstraint(
            'source_id', 'source_type', 'destination_id', 'destination_type'),
        db.Index(
            'ix_relationships_source',
            'source_type', 'source_id'),
        db.Index(
            'ix_relationships_destination',
            'destination_type', 'destination_id'),
    )

  _api_attrs = reflection.ApiAttributes(
      'source',
      'destination',
      reflection.Attribute(
          'is_external', create=True, update=False, read=True),
  )

  def _display_name(self):
    return "{}:{} <-> {}:{}".format(self.source_type, self.source_id,
                                    self.destination_type, self.destination_id)


  def validate_relatable_type(self, field, value):
    if value is None:
      raise ValidationError(u"{}.{} can't be None."
                            .format(self.__class__.__name__, field))
    if not isinstance(value, Relatable):
      raise ValidationError(u"You are trying to create relationship with not "
                            u"Relatable type: {}".format(value.type))
    tgt_type = self.source_type
    tgt_id = self.source_id
    if field == "source":
      tgt_type = self.destination_type
      tgt_id = self.destination_id
    if value and getattr(value, "type") == "Snapshot":
      if not tgt_type:
        return
      if value.child_type == tgt_type and value.child_id == tgt_id:
        raise ValidationError(
            u"Invalid source-destination types pair for {}: "
            u"source_type={!r}, destination_type={!r}"
            .format(self.type, self.source_type, self.destination_type)
        )
    # else check if the opposite is a Snapshot
    elif tgt_type == "Snapshot":
      from ggrc.models import Snapshot
      snapshot = db.session.query(Snapshot).get(tgt_id)
      if snapshot.child_type == value.type and snapshot.child_id == value.id:
        raise ValidationError(
            u"Invalid source-destination types pair for {}: "
            u"source_type={!r}, destination_type={!r}"
            .format(self.type, self.source_type, self.destination_type)
        )

  # pylint:disable=unused-argument
  @validates("is_external")
  def validate_is_external(self, key, value):
    """Validates is change of is_external column value allowed."""
    if is_external_app_user() and (not value or self.is_external is False):
      raise ValidationError(
          'External application can create only external relationships.')
    return value

  # pylint:disable=unused-argument
  @staticmethod
  def validate_delete(mapper, connection, target):
    """Validates is delete of Relationship is allowed."""
    if is_external_app_user() and not target.is_external:
      raise ValidationError(
          'External application can delete only external relationships.')


class Relatable(object):
  """Mixin adding Relationship functionality to an object"""

  @declared_attr
  def related_sources(cls):  # pylint: disable=no-self-argument
    joinstr = 'and_(remote(Relationship.destination_id) == {type}.id, '\
        'remote(Relationship.destination_type) == "{type}")'
    joinstr = joinstr.format(type=cls.__name__)
    return db.relationship(
        'Relationship',
        primaryjoin=joinstr,
        foreign_keys='Relationship.destination_id',
        backref='{0}_destination'.format(cls.__name__),
        cascade='all, delete-orphan')

  @declared_attr
  def related_destinations(cls):  # pylint: disable=no-self-argument
    joinstr = 'and_(remote(Relationship.source_id) == {type}.id, '\
        'remote(Relationship.source_type) == "{type}")'
    joinstr = joinstr.format(type=cls.__name__)
    return db.relationship(
        'Relationship',
        primaryjoin=joinstr,
        foreign_keys='Relationship.source_id',
        backref='{0}_source'.format(cls.__name__),
        cascade='all, delete-orphan')

  def related_objects(self, _types=None):
    """Returns all or a subset of related objects of certain types.

    If types is specified, only return objects of selected types

    Args:
      _types: A set of object types
    Returns:
      A set (or subset if _types is specified) of related objects.
    """
    # pylint: disable=not-an-iterable
    source_objs = [obj.source for obj in self.related_sources]
    dest_objs = [obj.destination for obj in self.related_destinations]
    related = source_objs + dest_objs

    if _types:
      return {obj for obj in related if obj.type in _types}
    return set(related)

  _include_links = []

  @classmethod
  def eager_query(cls):
    from sqlalchemy import orm

    query = super(Relatable, cls).eager_query()
    return cls.eager_inclusions(query, Relatable._include_links).options(
        orm.subqueryload('related_sources'),
        orm.subqueryload('related_destinations'))


class Stub(collections.namedtuple("Stub", ["type", "id"])):
  """Minimal object representation."""

  @classmethod
  def from_source(cls, relationship):
    return Stub(relationship.source_type, relationship.source_id)

  @classmethod
  def from_destination(cls, relationship):
    return Stub(relationship.destination_type, relationship.destination_id)


class RelationshipsCache(object):
  """Cache of related objects"""
  # pylint: disable=too-few-public-methods

  def __init__(self):
    self.cache = collections.defaultdict(set)

  def populate_cache(self, stubs):
    """Fetch all mappings for objects in stubs, cache them in self.cache."""
    # Union is here to convince mysql to use two separate indices and
    # merge te results. Just using `or` results in a full-table scan
    # Manual column list avoids loading the full object which would also try to
    # load related objects
    cols = db.session.query(
        Relationship.source_type, Relationship.source_id,
        Relationship.destination_type, Relationship.destination_id)
    relationships = cols.filter(
        sa.tuple_(
            Relationship.source_type,
            Relationship.source_id
        ).in_(
            [(s.type, s.id) for s in stubs]
        )
    ).union_all(
        cols.filter(
            sa.tuple_(
                Relationship.destination_type,
                Relationship.destination_id
            ).in_(
                [(s.type, s.id) for s in stubs]
            )
        )
    ).all()
    for (src_type, src_id, dst_type, dst_id) in relationships:
      src = Stub(src_type, src_id)
      dst = Stub(dst_type, dst_id)
      # only store a neighbor if we queried for it since this way we know
      # we'll be storing complete neighborhood by the end of the loop
      if src in stubs:
        self.cache[src].add(dst)
      if dst in stubs:
        self.cache[dst].add(src)
