# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Main snapshotter module

Snapshotter creates an immutable scope around an object (e.g. Audit) where
snapshot object represent a join between parent object (Audit),
child object (e.g. Control, Regulation, ...) and a particular revision.
"""

from logging import getLogger

import sqlalchemy as sa
from sqlalchemy.sql.expression import tuple_
from sqlalchemy.sql.expression import bindparam

from ggrc import db
from ggrc import models
from ggrc.models.hooks import acl
from ggrc.login import get_current_user_id
from ggrc.models import all_models
from ggrc.utils import benchmark

from ggrc.snapshotter.datastructures import Attr
from ggrc.snapshotter.datastructures import Pair
from ggrc.snapshotter.datastructures import Stub
from ggrc.snapshotter.datastructures import OperationResponse
from ggrc.snapshotter.helpers import create_snapshot_dict
from ggrc.snapshotter.helpers import create_snapshot_revision_dict
from ggrc.snapshotter.helpers import get_revisions
from ggrc.snapshotter.helpers import get_snapshots
from ggrc.snapshotter.indexer import reindex_snapshots_task

from ggrc.snapshotter.rules import get_rules
from google.appengine.ext import deferred

logger = getLogger(__name__)


class SnapshotGenerator(object):
  """Geneate snapshots per rules of all connected objects"""

  def __init__(self, dry_run):
    self.rules = get_rules()

    self.parents = set()
    self.children = set()
    self.snapshots = dict()
    self.context_cache = dict()
    self.dry_run = dry_run

  def add_parent(self, obj):
    """Add parent object and automatically scan neighborhood for snapshottable
    objects."""
    with benchmark("Snapshot.add_parent_object"):
      key = Stub.from_object(obj)
      if key not in self.parents:
        with benchmark("Snapshot.add_parent_object.add object"):
          objs = self._get_snapshottable_objects(obj)
          self.parents.add(key)
          self.context_cache[key] = obj.context_id
          self.children = self.children | objs
          self.snapshots[key] = objs
      return self.parents

  def add_family(self, parent, children):
    """Directly add parent object and children that should be snapshotted."""
    _type, _id = parent
    model = getattr(models, _type)
    parent_object = db.session.query(model).filter(model.id == _id).one()
    self.parents.add(parent)
    self.snapshots[parent] = children
    self.children = children
    self.context_cache[parent] = parent_object.context_id

  def _fetch_neighborhood(self, parent_object, objects):
    """Fetch relationships for objects and parent."""
    with benchmark("Snapshot._fetch_object_neighborhood"):
      query_pairs = set()

      for obj in objects:
        for snd_obj in self.rules.rules[parent_object.type]["snd"]:
          query_pairs.add((obj.type, obj.id, snd_obj))

      columns = db.session.query(
          models.Relationship.source_type,
          models.Relationship.source_id,
          models.Relationship.destination_type,
          models.Relationship.destination_id)

      relationships = columns.filter(
          tuple_(
              models.Relationship.destination_type,
              models.Relationship.destination_id,
              models.Relationship.source_type,
          ).in_(query_pairs)).union(
          columns.filter(tuple_(
              models.Relationship.source_type,
              models.Relationship.source_id,
              models.Relationship.destination_type,
          ).in_(query_pairs)))

      neighborhood = set()
      for (stype, sid, dtype, did) in relationships:
        source = Stub(stype, sid)
        destination = Stub(dtype, did)

        if source in objects:
          neighborhood.add(destination)
        else:
          neighborhood.add(source)
      return neighborhood

  def _get_snapshottable_objects(self, obj):
    """Get snapshottable objects from parent object's neighborhood."""
    with benchmark("Snapshot._get_snapshotable_objects"):
      related_mappings = set()
      object_rules = self.rules.rules[obj.type]

      with benchmark("Snapshot._get_snapshotable_objects.related_mappings"):
        relatable_rules = {
            rule for rule in object_rules["fst"]
            if isinstance(rule, basestring)
        }

        if relatable_rules:
          related_mappings = obj.related_objects({
              rule for rule in object_rules["fst"]
              if isinstance(rule, basestring)})

      with benchmark("Snapshot._get_snapshotable_objects.direct mappings"):
        direct_mappings = {getattr(obj, rule.name)
                           for rule in object_rules["fst"]
                           if isinstance(rule, Attr)}

      related_objects = {Stub.from_object(obj)
                         for obj in related_mappings | direct_mappings}

      with benchmark("Snapshot._get_snapshotable_objects.fetch neighborhood"):
        return self._fetch_neighborhood(obj, related_objects)

  def update(self, event, revisions, _filter=None):
    """Update parent object's snapshots."""
    _, for_update = self.analyze()
    result = self._update(for_update=for_update, event=event,
                          revisions=revisions, _filter=_filter)
    updated_ids = result.response
    if not self.dry_run:
      deferred.defer(reindex_snapshots_task, updated_ids)
      self._copy_snapshot_relationships()
      self._create_audit_relationships()
    return result

  def _update(self, for_update, event, revisions, _filter):
    """Update (or create) parent objects' snapshots and create revisions for
    them.

    Args:
      event: A ggrc.models.Event instance
      revisions: A set of tuples of pairs with revisions to which it should
        either create or update a snapshot of that particular audit
      _filter: Callable that should return True if it should be updated
    Returns:
      OperationResponse
    """
    # pylint: disable=too-many-locals
    with benchmark("Snapshot._update"):
      user_id = get_current_user_id()
      missed_keys = set()
      snapshot_cache = dict()
      modified_snapshot_keys = set()
      data_payload_update = list()
      revision_payload = list()
      response_data = dict()

      if self.dry_run and event is None:
        event_id = 0
      else:
        event_id = event.id

      with benchmark("Snapshot._update.filter"):
        if _filter:
          for_update = {elem for elem in for_update if _filter(elem)}

      with benchmark("Snapshot._update.get existing snapshots"):
        existing_snapshots = db.session.query(
            models.Snapshot.id,
            models.Snapshot.revision_id,
            models.Snapshot.parent_type,
            models.Snapshot.parent_id,
            models.Snapshot.child_type,
            models.Snapshot.child_id,
        ).filter(tuple_(
            models.Snapshot.parent_type, models.Snapshot.parent_id,
            models.Snapshot.child_type, models.Snapshot.child_id
        ).in_({pair.to_4tuple() for pair in for_update}))

        for esnap in existing_snapshots:
          sid, rev_id, pair_tuple = esnap[0], esnap[1], esnap[2:]
          pair = Pair.from_4tuple(pair_tuple)
          snapshot_cache[pair] = (sid, rev_id)

      with benchmark("Snapshot._update.retrieve latest revisions"):
        revision_id_cache = get_revisions(
            for_update,
            filters=[models.Revision.action.in_(["created", "modified"])],
            revisions=revisions)

      response_data["revisions"] = {
          "old": {pair: values[1] for pair, values in snapshot_cache.items()},
          "new": revision_id_cache
      }

      with benchmark("Snapshot._update.build snapshot payload"):
        for key in for_update:
          if key in revision_id_cache:
            sid, rev_id = snapshot_cache[key]
            latest_rev = revision_id_cache[key]
            if rev_id != latest_rev:
              modified_snapshot_keys.add(key)
              data_payload_update += [{
                  "_id": sid,
                  "_revision_id": latest_rev,
                  "_modified_by_id": user_id
              }]
          else:
            missed_keys.add(key)

      if missed_keys:
        logger.warning(
            "Tried to update snapshots for the following objects but "
            "found no revisions: %s", missed_keys)

      if not modified_snapshot_keys:
        return OperationResponse("update", True, set(), response_data)

      with benchmark("Snapshot._update.write snapshots to database"):
        update_sql = models.Snapshot.__table__.update().where(
            models.Snapshot.id == bindparam("_id")).values(
            revision_id=bindparam("_revision_id"),
            modified_by_id=bindparam("_modified_by_id"))
        self._execute(update_sql, data_payload_update)

      with benchmark("Snapshot._update.retrieve inserted snapshots"):
        snapshots = get_snapshots(modified_snapshot_keys)

      snapshot_ids = []
      with benchmark("Snapshot._update.create snapshots revision payload"):
        for snapshot in snapshots:
          snapshot_ids.append(snapshot.id)
          parent = Stub(snapshot.parent_type, snapshot.parent_id)
          context_id = self.context_cache[parent]
          data = create_snapshot_revision_dict("modified", event_id, snapshot,
                                               user_id, context_id)
          revision_payload += [data]

      with benchmark("Insert Snapshot entries into Revision"):
        self._execute(models.Revision.__table__.insert(), revision_payload)
      return OperationResponse("update", True, snapshot_ids, response_data)

  def analyze(self):
    """Analyze which snapshots need to be updated and which created"""
    query = set(db.session.query(
        models.Snapshot.parent_type,
        models.Snapshot.parent_id,
        models.Snapshot.child_type,
        models.Snapshot.child_id,
    ).filter(tuple_(
        models.Snapshot.parent_type, models.Snapshot.parent_id
    ).in_(self.parents)))

    existing_scope = {Pair.from_4tuple(fields) for fields in query}

    full_scope = {Pair(parent, child)
                  for parent, children in self.snapshots.items()
                  for child in children}

    for_update = existing_scope
    for_create = full_scope - existing_scope

    return for_create, for_update

  def upsert(self, event, revisions, _filter):
    return self._upsert(event=event, revisions=revisions, _filter=_filter)

  def _upsert(self, event, revisions, _filter):
    """Update and (if needed) create snapshots

    Args:
      event: A ggrc.models.Event instance
      revisions: A set of tuples of pairs with revisions to which it should
        either create or update a snapshot of that particular audit
      _filter: Callable that should return True if it should be updated
    Returns:
      OperationResponse
    """
    for_create, for_update = self.analyze()
    create, update = None, None
    created_ids, updated_ids = set(), set()

    if for_update:
      update = self._update(
          for_update=for_update, event=event, revisions=revisions,
          _filter=_filter)
      updated_ids = update.response
    if for_create:
      create = self._create(for_create=for_create, event=event,
                            revisions=revisions, _filter=_filter)
      created_ids = create.response

    to_reindex = set(updated_ids) | set(created_ids)
    if not self.dry_run:
      deferred.defer(reindex_snapshots_task, to_reindex)
      self._remove_lost_snapshot_mappings()
      self._copy_snapshot_relationships()
      self._create_audit_relationships()
    return OperationResponse("upsert", True, {
        "create": create,
        "update": update
    }, {
        "dry-run": self.dry_run
    })

  def _execute(self, operation, data):
    """Execute bulk operation on data if not in dry mode

    Args:
      operation: sqlalchemy operation
      data: a list of dictionaries with keys representing column names and
        values to insert with operation
    """
    if data and not self.dry_run:
      db.session.execute(operation, data)

  def create(self, event, revisions, _filter=None):
    """Create snapshots of parent object's neighborhood per provided rules
    and split in chunks if there are too many snapshottable objects."""
    for_create, _ = self.analyze()
    result = self._create(
        for_create=for_create, event=event,
        revisions=revisions, _filter=_filter)
    db.session.commit()
    snapshot_ids = result.response
    if not self.dry_run:
      deferred.defer(reindex_snapshots_task, snapshot_ids)
      self._copy_snapshot_relationships()
      self._create_audit_relationships()
    return result

  def _create(self, for_create, event, revisions, _filter):
    """Create snapshots of parent objects neighhood and create revisions for
    snapshots.

    Args:
      event: A ggrc.models.Event instance
      revisions: A set of tuples of pairs with revisions to which it should
        either create or update a snapshot of that particular audit
      _filter: Callable that should return True if it should be updated
    Returns:
      OperationResponse
    """
    # pylint: disable=too-many-locals,too-many-statements
    with benchmark("Snapshot._create"):
      with benchmark("Snapshot._create init"):
        user_id = get_current_user_id()
        missed_keys = set()
        data_payload = list()
        revision_payload = list()
        response_data = dict()

        if self.dry_run and event is None:
          event_id = 0
        else:
          event_id = event.id

      with benchmark("Snapshot._create.filter"):
        if _filter:
          for_create = {elem for elem in for_create if _filter(elem)}

      with benchmark("Snapshot._create._get_revisions"):
        revision_id_cache = get_revisions(for_create, revisions)

      response_data["revisions"] = revision_id_cache

      with benchmark("Snapshot._create.create payload"):
        for pair in for_create:
          if pair in revision_id_cache:
            revision_id = revision_id_cache[pair]
            context_id = self.context_cache[pair.parent]
            data = create_snapshot_dict(pair, revision_id, user_id, context_id)
            data_payload += [data]
          else:
            missed_keys.add(pair)

      if missed_keys:
        logger.warning(
            "Tried to create snapshots for the following objects but "
            "found no revisions: %s", missed_keys)

      with benchmark("Snapshot._create.write to database"):
        self._execute(
            models.Snapshot.__table__.insert(),
            data_payload
        )

      with benchmark("Snapshot._create.retrieve inserted snapshots"):
        snapshots = get_snapshots(for_create)

      snapshot_ids = []
      with benchmark("Snapshot._create.create revision payload"):
        with benchmark("Snapshot._create.create snapshots revision payload"):
          for snapshot in snapshots:
            snapshot_ids.append(snapshot.id)
            parent = Stub(snapshot.parent_type, snapshot.parent_id)
            context_id = self.context_cache[parent]
            data = create_snapshot_revision_dict("created", event_id, snapshot,
                                                 user_id, context_id)
            revision_payload += [data]

      with benchmark("Snapshot._create.write revisions to database"):
        self._execute(models.Revision.__table__.insert(), revision_payload)
      return OperationResponse("create", True, snapshot_ids, response_data)

  def _copy_snapshot_relationships(self):
    """Add relationships between snapshotted objects.

    Create relationships between individual snapshots if a relationship exists
    between a pair of object that was snapshotted. These relationships get
    created for all objects inside a single parent scope.
    """
    for parent in self.parents:
      query = """
          INSERT IGNORE INTO relationships (
              modified_by_id,
              created_at,
              updated_at,
              source_id,
              source_type,
              destination_id,
              destination_type,
              context_id
          )
          SELECT
              :user_id,
              now(),
              now(),
              snap_1.id,
              "Snapshot",
              snap_2.id,
              "Snapshot",
              snap_2.context_id
          FROM relationships AS rel
          INNER JOIN snapshots AS snap_1
              ON (snap_1.child_type, snap_1.child_id) =
                 (rel.source_type, rel.source_id)
          INNER JOIN snapshots AS snap_2
              ON (snap_2.child_type, snap_2.child_id) =
                 (rel.destination_type, rel.destination_id)
          WHERE
              snap_1.parent_id = :parent_id AND
              snap_2.parent_id = :parent_id
          """
      db.session.execute(query, {
          "user_id": get_current_user_id(),
          "parent_id": parent.id
      })

  @classmethod
  def _get_audit_relationships(cls, audit_ids):
    """Get all relationship ids for the give audits.
    Args:
      audit_ids: list or set of audit ids.

    Returns:
      set of relationship ids for the given audits.
    """
    relationships_table = all_models.Relationship.__table__
    select_statement = sa.select([
        relationships_table.c.id
    ]).where(
        sa.and_(
            relationships_table.c.destination_id.in_(audit_ids),
            relationships_table.c.destination_type == all_models.Audit.__name__
        )
    ).union(
        sa.select([
            relationships_table.c.id
        ]).where(
            sa.and_(
                relationships_table.c.source_id.in_(audit_ids),
                relationships_table.c.source_type == all_models.Audit.__name__
            )
        )
    )
    id_rows = db.session.execute(select_statement).fetchall()

    return {row.id for row in id_rows}

  def _create_audit_relationships(self):
    """Create relationships between snapshot objects and audits.

    Generally snapshots are related to audits by default, but we also duplicate
    this data in relationships table for ACL propagation.
    """

    relationships_table = all_models.Relationship.__table__
    snapshot_table = all_models.Snapshot.__table__
    inserter = relationships_table.insert().prefix_with("IGNORE")

    audit_ids = {parent.id for parent in self.parents}
    if not audit_ids:
      return

    old_ids = self._get_audit_relationships(audit_ids)

    select_statement = sa.select([
        sa.literal(get_current_user_id()),
        sa.func.now(),
        sa.func.now(),
        snapshot_table.c.parent_id,
        snapshot_table.c.parent_type,
        snapshot_table.c.id,
        sa.literal(all_models.Snapshot.__name__),
    ]).select_from(
        snapshot_table
    ).where(
        snapshot_table.c.parent_id.in_(audit_ids)
    )

    db.session.execute(
        inserter.from_select(
            [
                relationships_table.c.modified_by_id,
                relationships_table.c.created_at,
                relationships_table.c.updated_at,
                relationships_table.c.source_id,
                relationships_table.c.source_type,
                relationships_table.c.destination_id,
                relationships_table.c.destination_type,
            ],
            select_statement
        )
    )

    new_ids = self._get_audit_relationships(audit_ids)
    created_ids = new_ids.difference(old_ids)
    acl.add_relationships(created_ids)

  def _remove_lost_snapshot_mappings(self):
    """Remove mappings between snapshots if base objects were unmapped."""
    source_snap = sa.orm.aliased(all_models.Snapshot, name="source_snap")
    dest_snap = sa.orm.aliased(all_models.Snapshot, name="dest_snap")
    source_rel = sa.orm.aliased(all_models.Relationship, name="source_rel")
    dest_rel = sa.orm.aliased(all_models.Relationship, name="dest_rel")

    parents = {(p.type, p.id) for p in self.parents}
    lost_rel_ids = db.session.query(all_models.Relationship.id).join(
        source_snap, source_snap.id == all_models.Relationship.source_id
    ).join(
        dest_snap, dest_snap.id == all_models.Relationship.destination_id
    ).outerjoin(
        source_rel,
        sa.and_(
            source_rel.source_type == source_snap.child_type,
            source_rel.source_id == source_snap.child_id,
            source_rel.destination_type == dest_snap.child_type,
            source_rel.destination_id == dest_snap.child_id,
        )
    ).outerjoin(
        dest_rel,
        sa.and_(
            dest_rel.destination_type == source_snap.child_type,
            dest_rel.destination_id == source_snap.child_id,
            dest_rel.source_type == dest_snap.child_type,
            dest_rel.source_id == dest_snap.child_id,
        )
    ).filter(
        all_models.Relationship.source_type == 'Snapshot',
        all_models.Relationship.destination_type == 'Snapshot',
        source_rel.id.is_(None),
        dest_rel.id.is_(None),
        sa.tuple_(
            source_snap.parent_type,
            source_snap.parent_id,
        ).in_(parents),
        sa.tuple_(
            dest_snap.parent_type,
            dest_snap.parent_id,
        ).in_(parents)
    )

    lost_rels = all_models.Relationship.query.filter(
        all_models.Relationship.id.in_(lost_rel_ids)
    )
    for rel in lost_rels:
      db.session.delete(rel)


def create_snapshots(objs, event, revisions=None, _filter=None, dry_run=False):
  """Create snapshots of parent objects."""
  # pylint: disable=unused-argument
  if not revisions:
    revisions = set()

  with benchmark("Snapshot.create_snapshots"):
    with benchmark("Snapshot.create_snapshots.init"):
      generator = SnapshotGenerator(dry_run)
      if not isinstance(objs, set):
        objs = {objs}
      for obj in objs:
        db.session.add(obj)
        with benchmark("Snapshot.create_snapshots.add_parent_objects"):
          generator.add_parent(obj)
    with benchmark("Snapshot.create_snapshots.create"):
      return generator.create(event=event,
                              revisions=revisions,
                              _filter=_filter)


def upsert_snapshots(objs, event, revisions=None, _filter=None, dry_run=False):
  """Update (and create if needed) snapshots of parent objects."""
  # pylint: disable=unused-argument
  if not revisions:
    revisions = set()

  with benchmark("Snapshot.update_snapshots"):
    generator = SnapshotGenerator(dry_run)
    if not isinstance(objs, set):
      objs = {objs}
    for obj in objs:
      db.session.add(obj)
      generator.add_parent(obj)
    return generator.upsert(event=event, revisions=revisions, _filter=_filter)


def clone_scope(base_parent, new_parent, event):
  """Create exact copy of parent object scope.

  Args:
    base_parent: Old parent object
    new_parent: New parent object
    event: Event that triggered scope cloning
  """

  with benchmark("clone_scope.clone audit scope"):
    source_snapshots = db.session.query(
        models.Snapshot.child_type,
        models.Snapshot.child_id,
        models.Snapshot.revision_id
    ).filter(
        models.Snapshot.parent_type == base_parent.type,
        models.Snapshot.parent_id == base_parent.id)

    snapshot_revisions = {
        Pair.from_4tuple((new_parent.type, new_parent.id, ctype, cid)): revid
        for ctype, cid, revid in source_snapshots}

    parent = Stub(new_parent.type, new_parent.id)
    children = {pair.child for pair in snapshot_revisions}
    generator = SnapshotGenerator(dry_run=False)
    generator.add_family(parent, children)
    generator.create(event, snapshot_revisions)
