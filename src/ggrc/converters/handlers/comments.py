# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers comment entries."""

from ggrc import db

from sqlalchemy import orm

from ggrc.converters import errors
from ggrc.converters.handlers.handlers import ColumnHandler
from ggrc.models import all_models
from ggrc.login import get_current_user, get_current_user_id


class CommentColumnHandler(ColumnHandler):
  """ Handler for comments """

  COMMENTS_SEPARATOR = ";;"

  @staticmethod
  def split_comments(raw_value):
    """Split comments"""
    res = [comment.strip() for comment in
           raw_value.rsplit(CommentColumnHandler.COMMENTS_SEPARATOR)
           if comment.strip()]
    return res

  def parse_item(self):
    """Parse a list of comments to be mapped.

    Parse a COMMENTS_SEPARATOR separated list of comments

    Returns:
      list of comments
    """
    comments = self.split_comments(self.raw_value)
    if self.raw_value and not comments:
      self.add_warning(errors.WRONG_VALUE,
                       column_name=self.display_name)
    return comments

  def get_value(self):
    return ""

  @staticmethod
  def _get_assignees(object_id, object_type, user_id):
    """Getting object roles of the comment's author.

    Args:
      object_id: id of imported object
      object_type: type of imported object
      user_id: id of the comment's author
    Returns:
      list of roles' names
    """
    acl = db.session.query(all_models.AccessControlList).options(
        orm.joinedload('ac_role'),
        orm.joinedload('person'),
    ).filter(
        all_models.AccessControlList.object_id == object_id,
        all_models.AccessControlList.object_type == object_type,
        all_models.AccessControlList.person_id == user_id
    ).all()

    assignees = []
    for item in acl:
      if not item.ac_role.internal:
        assignees.append(item.ac_role.name)

    return assignees

  def set_obj_attr(self):
    """ Create comments """
    if self.dry_run or not self.value:
      return
    current_obj = self.row_converter.obj
    for description in self.value:
      current_user = get_current_user()
      assignees = self._get_assignees(current_obj.id, current_obj.type,
                                      current_user.id)
      assignee_type = ",".join(assignees) or None

      comment = all_models.Comment(description=description,
                                   assignee_type=assignee_type,
                                   modified_by_id=get_current_user_id())
      db.session.add(comment)
      mapping = all_models.Relationship(source=current_obj,
                                        destination=comment)
      db.session.add(mapping)
