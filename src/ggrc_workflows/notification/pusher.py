# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

import datetime
import collections
from dateutil import relativedelta

import flask

from sqlalchemy import or_
from sqlalchemy import tuple_
from sqlalchemy.sql.expression import true

from ggrc import db
from ggrc.models.notification import Notification
from ggrc.models.notification import NotificationType


REPEATABLE_NOTIFICATIONS = {"cycle_task_overdue", }


def get_notification_query(*objs, **kwargs):
  # maybe we shouldn't return different thigs here.
  keys = [(obj.id, obj.type) for obj in objs]
  notif_key = tuple_(Notification.object_id, Notification.object_type)
  query = Notification.query.filter(
      or_(Notification.sent_at.is_(None), Notification.repeating == true())
  ).filter(
      notif_key.in_(keys)
  )
  notification_names = kwargs.get('notification_names') or []
  if notification_names:
    query = query.filter(Notification.notification_type_id.in_([
        n.id for n in get_notification_types(*notification_names)
    ]))
  return query


def notification_exists_for(*obj, **kwargs):
  return db.session.query(
      get_notification_query(*obj, **kwargs).exists()
  ).scalar()


def get_notification_types(*names):
  if not getattr(flask.g, "notification_types", None):
    notification_types = NotificationType.query.all()
    flask.g.notification_types = collections.defaultdict(dict)
    for notif_type in notification_types:
      flask.g.notification_types[notif_type.name] = notif_type
  return [flask.g.notification_types[name] for name in names]


def get_notification_type(name):
  return get_notification_types(name)[0]


def push(obj, notif_type, send_on=None, repeating=False):
  return Notification(
      object=obj,
      notification_type=notif_type,
      send_on=send_on or datetime.date.today(),
      repeating=repeating,
  )


def get_notification_context(notification_type, send_at):
  """Return notification context dict for sent data."""
  today = datetime.datetime.combine(datetime.date.today(),
                                    datetime.datetime.min.time())
  repeatable_notification = notification_type.name in REPEATABLE_NOTIFICATIONS
  send_on_date = send_at - relativedelta.relativedelta(
      days=notification_type.advance_notice
  )
  send_on = datetime.datetime.combine(send_on_date,
                                      datetime.datetime.min.time())
  if repeatable_notification:
    send_on = max(send_on, today)
  return {"notif_type": notification_type,
          "send_on": send_on,
          "repeating": repeatable_notification}


def update_or_create_notifications(obj, send_at, *notification_names):
  today = datetime.datetime.combine(datetime.date.today(),
                                    datetime.datetime.min.time())
  types = {n.name: n for n in get_notification_types(*notification_names)}
  for notification_name in notification_names:
    notif_type = types[notification_name]
    notification_context = get_notification_context(notif_type, send_at)
    query = get_notification_query(
        obj
    ).filter(
        Notification.notification_type_id == notif_type.id
    )
    send_on = notification_context["send_on"]
    if send_on < today:
      # this should not be allowed, but if a cycle task is changed to a past
      # date, we remove the current pending notification if it exists
      query.delete(synchronize_session="fetch")
    elif not query.update({Notification.send_on: send_on},
                          synchronize_session="fetch"):
      # when cycle date is moved in the future and no current create new
      # notification
      push(obj, **notification_context)


def create_notifications_for_objects(notification_type, send_at, *objs):
  """Only creates objects for selected notification_name.

  Args:
      notification_type can be base_string or instance of notification type.
      objs list of notified instances
  """

  if not objs:
    return
  if isinstance(notification_type, basestring):
    notification_type = get_notification_type(notification_type)
  if not isinstance(notification_type, NotificationType):
    raise TypeError("notification_type should be basestring or "
                    "NotificationType instance.")
  notification_context = get_notification_context(notification_type, send_at)
  today = datetime.datetime.combine(datetime.date.today(),
                                    datetime.datetime.min.time())
  send_on = notification_context["send_on"]
  if send_on < today:
    return
  for obj in objs:
    push(obj, **notification_context)
