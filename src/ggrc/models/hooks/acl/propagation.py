# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""Entry point for all acl handlers.

This package should have the single hook that should handle all acl propagation
and deletion.
"""

import logging

import flask
import sqlalchemy as sa

from ggrc import db
from ggrc import login
from ggrc import utils
from ggrc.utils import helpers
from ggrc.access_control import utils as acl_utils
from ggrc.cache.utils import clear_permission_cache
from ggrc.cache.utils import clear_users_permission_cache
from ggrc.models import all_models
from ggrc.models.hooks import access_control_role

logger = logging.getLogger(__name__)

# Safety cutoff limit for maximum propagation depth. If this depth is exceeded
# it suggests invalid propagation tree entries, or the propagation tree could
# contain cycles.
PROPAGATION_DEPTH_LIMIT = 50


def _rel_parent(parent_acl_ids=None, relationship_ids=None, source=True,
                user_id=None):
  """Get left side of relationships mappings through source."""
  rel_table = all_models.Relationship.__table__
  acl_table = all_models.AccessControlList.__table__
  parent_acr = all_models.AccessControlRole.__table__.alias(
      "parent_acr_{}".format(source)
  )
  child_acr = all_models.AccessControlRole.__table__.alias(
      "child_acr_{}".format(source)
  )
  # The grandchild is only used to check the child part of the relationship. We
  # might want to check if it would be more efficient to store grandchild info
  # in the child ACR entry instead of making an extra join on our tables.
  grandchild_acr = all_models.AccessControlRole.__table__.alias(
      "grandchild_acr_{}".format(source)
  )
  where_conditions = [
  ]
  if relationship_ids is not None:
    where_conditions.append(rel_table.c.id.in_(relationship_ids))
    if parent_acl_ids:
      where_conditions.append(~acl_table.c.id.in_(parent_acl_ids))
  elif parent_acl_ids is not None:
    where_conditions.append(acl_table.c.id.in_(parent_acl_ids))

  if source:
    parent_object_id = rel_table.c.source_id
    parent_object_type = rel_table.c.source_type
    grandchild_object_type = rel_table.c.destination_type
  else:
    parent_object_id = rel_table.c.destination_id
    parent_object_type = rel_table.c.destination_type
    grandchild_object_type = rel_table.c.source_type

  select_statement = sa.select([
      child_acr.c.id.label("ac_role_id"),
      rel_table.c.id.label("object_id"),
      sa.literal(all_models.Relationship.__name__).label("object_type"),
      sa.func.now().label("created_at"),
      sa.literal(user_id).label("modified_by_id"),
      sa.func.now().label("updated_at"),
      acl_table.c.id.label("parent_id"),
      acl_table.c.id.label("parent_id_nn"),
      acl_table.c.base_id.label("base_id"),
  ]).select_from(
      sa.join(
          sa.join(
              sa.join(
                  sa.join(
                      rel_table,
                      acl_table,
                      sa.and_(
                          acl_table.c.object_id == parent_object_id,
                          acl_table.c.object_type == parent_object_type,
                      )
                  ),
                  parent_acr,
                  parent_acr.c.id == acl_table.c.ac_role_id
              ),
              child_acr,
              sa.and_(
                  child_acr.c.parent_id == parent_acr.c.id,
                  child_acr.c.object_type == all_models.Relationship.__name__,
              ),
          ),
          grandchild_acr,
          sa.and_(
              grandchild_acr.c.parent_id == child_acr.c.id,
              grandchild_acr.c.object_type == grandchild_object_type,
          )
      )
  ).where(
      sa.and_(*where_conditions)
  )
  return select_statement


def _rel_child(parent_acl_ids, source=True, user_id=None):
  """Get left side of relationships mappings through source."""
  rel_table = all_models.Relationship.__table__
  acl_table = all_models.AccessControlList.__table__
  parent_acr = all_models.AccessControlRole.__table__.alias(
      "parent_acr_{}".format(source)
  )
  child_acr = all_models.AccessControlRole.__table__.alias(
      "child_acr_{}".format(source)
  )

  if source:
    object_id = rel_table.c.destination_id
    object_type = rel_table.c.destination_type
  else:
    object_id = rel_table.c.source_id
    object_type = rel_table.c.source_type

  acl_link = sa.and_(
      acl_table.c.object_id == rel_table.c.id,
      acl_table.c.object_type == all_models.Relationship.__name__,
  )

  select_statement = sa.select([
      child_acr.c.id.label("ac_role_id"),
      object_id.label("object_id"),
      object_type.label("object_type"),
      sa.func.now().label("created_at"),
      sa.literal(user_id).label("modified_by_id"),
      sa.func.now().label("updated_at"),
      acl_table.c.id.label("parent_id"),
      acl_table.c.id.label("parent_id_nn"),
      acl_table.c.base_id.label("base_id"),
  ]).select_from(
      sa.join(
          sa.join(
              sa.join(
                  rel_table,
                  acl_table,
                  acl_link
              ),
              parent_acr,
              parent_acr.c.id == acl_table.c.ac_role_id
          ),
          child_acr,
          child_acr.c.parent_id == parent_acr.c.id
      )
  ).where(
      sa.and_(
          acl_table.c.id.in_(parent_acl_ids),
          child_acr.c.object_type == object_type,
      )
  )
  return select_statement


def _get_relationship_acl_ids(relationship_ids):
  """Get ACL ids for the given relationship ids.

  Note that in the first layer of propagation this function acts the same way
  as _get_child_ids does in all higher levels.

  Args:
    relationship_ids: list of parent acl entries or query with parent ids.
  Returns:
    list of ACL ids that belong to given relationships.
  """
  acl_table = all_models.AccessControlList.__table__

  return sa.select([acl_table.c.id]).where(
      sa.and_(
          acl_table.c.object_type == all_models.Relationship.__name__,
          acl_table.c.object_id.in_(relationship_ids),
      )
  )


def _get_child_ids(parent_ids):
  """Get all acl ids for acl entries with the given parent ids

  Args:
    parent_ids: list of parent acl entries or query with parent ids.
  Returns:
    list of ACL ids for all children from the given parents.
  """
  acl_table = all_models.AccessControlList.__table__

  children = db.session.execute(
      sa.select([acl_table.c.id]).where(
          acl_table.c.parent_id.in_(parent_ids)
      )
  ).fetchall()

  return [child.id for child in children]


def _handle_propagation_parents(parent_acl_ids, user_id):
  """Propagate ACL records from parent objects to relationships."""
  src_select = _rel_parent(parent_acl_ids, source=True, user_id=user_id)
  dst_select = _rel_parent(parent_acl_ids, source=False, user_id=user_id)
  select_statement = sa.union(src_select, dst_select)
  acl_utils.insert_select_acls(select_statement)


def _handle_propagation_children(new_parent_ids, user_id):
  """Propagate ACL records from relationships to child objects."""
  src_select = _rel_child(new_parent_ids, source=True, user_id=user_id)
  dst_select = _rel_child(new_parent_ids, source=False, user_id=user_id)
  select_statement = sa.union(src_select, dst_select)
  acl_utils.insert_select_acls(select_statement)


def _handle_propagation_rel(relationship_ids, new_acl_ids, user_id):
  """Handle propagation for relationship object."""
  src_select = _rel_parent(
      parent_acl_ids=new_acl_ids,
      relationship_ids=relationship_ids,
      source=True,
      user_id=user_id,
  )
  dst_select = _rel_parent(
      parent_acl_ids=new_acl_ids,
      relationship_ids=relationship_ids,
      source=False,
      user_id=user_id,
  )
  select_statement = sa.union(src_select, dst_select)
  acl_utils.insert_select_acls(select_statement)


def _handle_acl_step(parent_acl_ids, user_id):
  """Handle role propagation through relationships.

  For handling relationships of type:
  Audit > Relationship > Object
  The parent part of this function refers to propagation from Audit to
  Relationship. The child part refers to propagation from Relationship to
  Object (either Assessment, Issue, Document, Comment)
  """

  _handle_propagation_parents(parent_acl_ids, user_id)
  new_parent_ids = _get_child_ids(parent_acl_ids)
  _handle_propagation_children(new_parent_ids, user_id)

  return _get_child_ids(new_parent_ids)


def _handle_relationship_step(relationship_ids, new_acl_ids, user_id):
  """Propagate first level or ACLs caused by new relationships."""

  _handle_propagation_rel(relationship_ids, new_acl_ids, user_id)
  new_parent_ids = _get_relationship_acl_ids(relationship_ids)
  _handle_propagation_children(new_parent_ids, user_id)

  return _get_child_ids(new_parent_ids)


def _propagate(parent_acl_ids, user_id):
  """Propagate ACL entries through the entire propagation tree."""

  # The following for statement is a replacement for `while True` statement
  # with a safety cutoff limit.
  for _ in range(PROPAGATION_DEPTH_LIMIT):

    child_ids = _handle_acl_step(parent_acl_ids, user_id)

    if child_ids:
      parent_acl_ids = child_ids
    else:
      # Exit the loop when there are no more ACL entries to propagate
      return

  # We should only be able to get here if the propagation failed to finish in
  # PROPAGATION_DEPTH_LIMIT iterations.
  raise Exception("Propagation depth limit exceeded. Check the propagation "
                  "tree for cycles, invalid entries or too deep entries.")


def _propagate_relationships(relationship_ids, new_acl_ids, user_id):
  """Start ACL propagation for newly created relationships.

  Note this function will only propagate old ACL entries. All newly created
  ones will be propagated after relationship propagation finishes.
  """
  if not relationship_ids:
    return
  child_ids = _handle_relationship_step(relationship_ids, new_acl_ids, user_id)
  _propagate(child_ids, user_id)
  # retrieve user ids from propagated ACPs
  user_ids = acl_utils.get_user_ids(
      all_models.AccessControlList.id.in_(child_ids)
  )
  getattr(flask.g, "user_ids").update(user_ids)


def _delete_orphan_acl_entries(deleted_objects):
  """Delete ACL entries for deleted objects.

  This is a quicker way to ensure all ACL entries are removed when our ORM
  object is deleted. The default way with using ORM mapper would require all
  internal roles to be loaded before they can be deleted. But since we can do
  that with a simple filter, using this method is more efficient.
  """
  if not deleted_objects:
    return

  acl_table = all_models.AccessControlList.__table__
  db.session.execute(
      acl_table.delete().where(
          sa.tuple_(
              acl_table.c.object_type,
              acl_table.c.object_id
          ).in_(
              deleted_objects
          )

      )
  )
  db.session.plain_commit()


def _delete_propagated_acls(acl_ids):
  """Delete propagated acl entries for the given parents.

  Args:
    acl_ids: List of parent acl ids for which the propagated acl entries will
      be deleted.
  """
  acl_table = all_models.AccessControlList.__table__

  db.session.execute(
      acl_table.delete().where(
          acl_table.c.parent_id.in_(acl_ids),
      )
  )
  db.session.plain_commit()


def _set_empty_base_ids():
  """Set base_id for new entries."""
  db.session.execute(
      "UPDATE access_control_list SET base_id = id WHERE base_id IS NULL"
  )
  db.session.plain_commit()


def propagate(full_propagate=False):
  """Propagate all ACLs caused by objects in new_objects list.

  Args:
    new_acl_ids: list of newly created ACL ids,
    new_relationship_ids: list of newly created relationship ids,
  """
  if not (hasattr(flask.g, "new_acl_ids") and
          hasattr(flask.g, "new_relationship_ids") and
          hasattr(flask.g, "deleted_objects")):
    return

  if flask.g.deleted_objects:
    with utils.benchmark("Delete internal ACL entries for deleted objects"):
      _delete_orphan_acl_entries(flask.g.deleted_objects)

  _set_empty_base_ids()

  current_user_id = login.get_current_user_id()

  # The order of propagation of relationships and other ACLs is important
  # because relationship code excludes other ACLs from propagating.
  if flask.g.new_relationship_ids:
    with utils.benchmark("Propagate ACLs for new relationships"):
      _propagate_relationships(
          flask.g.new_relationship_ids,
          flask.g.new_acl_ids,
          current_user_id,
      )
  if flask.g.new_acl_ids:
    with utils.benchmark("Propagate new ACL entries"):
      _propagate(flask.g.new_acl_ids, current_user_id)

  # clear permissions memcache
  if not full_propagate and flask.g.user_ids:
    with utils.benchmark("Clear ACL memcache for specific users: %s" %
                         flask.g.user_ids):
      clear_users_permission_cache(flask.g.user_ids)

  del flask.g.new_acl_ids
  del flask.g.new_relationship_ids
  del flask.g.user_ids
  del flask.g.deleted_objects


def _add_missing_acl_entries():
  """Add missing ACL entries.

  Since we now rely on eager ACL creation, this function helps for creating
  those entries for older objects that have not had any person on a given role.
  """
  roles = all_models.AccessControlRole.query.filter(
      all_models.AccessControlRole.internal == 0,
      all_models.AccessControlRole.parent_id.is_(None),
  )
  for role in roles:
    logger.info("Add missing acl entries on %s for role %s",
                role.object_type, role.name)
    access_control_role.handle_role_acls(role)


@helpers.without_sqlalchemy_cache
def propagate_all():
  """Re-evaluate propagation for all objects."""
  with utils.benchmark("Clear ACL memcache"):
    clear_permission_cache()
  with utils.benchmark("Run propagate_all"):
    with utils.benchmark("Add missing acl entries"):
      _add_missing_acl_entries()
    with utils.benchmark("Get non propagated acl ids"):
      query = db.session.query(
          all_models.AccessControlList.id,
      ).filter(
          all_models.AccessControlList.parent_id.is_(None),
      )
      all_acl_ids = [acl.id for acl in query]

    with utils.benchmark("Propagate normal acl entries"):
      count = len(all_acl_ids)
      propagated_count = 0
      for acl_ids in utils.list_chunks(all_acl_ids, chunk_size=50):
        propagated_count += len(acl_ids)
        logger.info("Propagating ACL entries: %s/%s", propagated_count, count)
        _delete_propagated_acls(acl_ids)

        flask.g.new_acl_ids = acl_ids
        flask.g.new_relationship_ids = set()
        flask.g.user_ids = set()
        flask.g.deleted_objects = set()
        propagate(full_propagate=True)
