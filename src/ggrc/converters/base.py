# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Base objects for csv file converters."""

from collections import defaultdict

from google.appengine.ext import deferred

from ggrc import login
from ggrc import settings
from ggrc.utils import benchmark
from ggrc.utils import structures
from ggrc.cache.memcache import MemCache
from ggrc.converters import get_exportables
from ggrc.converters import import_helper
from ggrc.converters.base_block import BlockConverter
from ggrc.converters.snapshot_block import SnapshotBlockConverter
from ggrc.converters.import_helper import extract_relevant_data
from ggrc.converters.import_helper import split_array
from ggrc.converters.import_helper import CsvStringBuilder
from ggrc.fulltext import get_indexer


class BaseConverter(object):
  """Base class for csv converters."""
  def __init__(self, **kwargs):
    self.dry_run = kwargs.get("dry_run", True)
    self.csv_data = kwargs.get("csv_data", [])
    self.ids_by_type = kwargs.get("ids_by_type", [])
    self.block_converters = []
    self.new_objects = defaultdict(structures.CaseInsensitiveDict)
    self.shared_state = {}
    self.response_data = []
    self.exportable = get_exportables()
    self.indexer = get_indexer()

  def get_info(self):
    for converter in self.block_converters:
      self.response_data.append(converter.get_info())
    return self.response_data

  def get_object_names(self):
    return [c.name for c in self.block_converters]

  @classmethod
  def drop_cache(cls):
    if not getattr(settings, 'MEMCACHE_MECHANISM', False):
      return
    memcache = MemCache()
    memcache.clean()


class ImportConverter(BaseConverter):
  """Import Converter.

  This class contains and handles all block converters and makes sure that
  blocks and columns are handled in the correct order.
  """

  CLASS_ORDER = [
      "Person",
      "Program",
      "Risk Assessment",
      "Audit",
      "Issue",
      "Assessment",
      "Policy",
      "Regulation",
      "Standard",
      "Section",
      "Control",
      "Assessment Template",
      "Custom Attribute Definition",
      "Assessment",
      "Workflow",
      "Task Group",
      "Task Group Task",
  ]

  priority_columns = [
      "email",
      "slug",
      "delete",
      "task_type",
      "audit",
  ]

  secondary_objects = [
      "comments",
  ]

  def initialize_block_converters(self):
    """ Initialize block converters.

    Prepare BlockConverters and order them like specified in self.CLASS_ORDER.
    """
    offsets, data_blocks = split_array(self.csv_data)
    for offset, data in zip(offsets, data_blocks):
      if len(data) < 2:
        continue  # empty block
      class_name = data[1][0].strip().lower()
      object_class = self.exportable.get(class_name)
      raw_headers, rows = extract_relevant_data(data)
      block_converter = BlockConverter(self, object_class=object_class,
                                       rows=rows, raw_headers=raw_headers,
                                       offset=offset, class_name=class_name)
      block_converter.check_block_restrictions()
      self.block_converters.append(block_converter)

    order = defaultdict(int)
    order.update({c: i for i, c in enumerate(self.CLASS_ORDER)})
    order["Person"] = -1
    self.block_converters.sort(key=lambda x: order[x.name])

  def import_csv_data(self):
    self.initialize_block_converters()
    self.row_converters_from_csv()
    self.handle_priority_columns()
    self.import_objects()
    self.import_mapped_objects()
    self.import_secondary_objects()
    self._start_compute_attributes_job()
    self.drop_cache()

  def row_converters_from_csv(self):
    for converter in self.block_converters:
      converter.row_converters_from_csv()

  def handle_priority_columns(self):
    for block_converter in self.block_converters:
      block_converter.handle_row_data(field_list=self.priority_columns)

  def _start_compute_attributes_job(self):
    revision_ids = []
    for block_converter in self.block_converters:
      revision_ids.extend(block_converter.revision_ids)
    if revision_ids:
      cur_user = login.get_current_user()
      deferred.defer(
          import_helper.calculate_computed_attributes,
          revision_ids,
          cur_user.id
      )

  def import_objects(self):
    """Import objects with their primary attributes"""
    for converter in self.block_converters:
      converter.handle_row_data(ignore_list=self.secondary_objects)
      converter.import_objects()

  def import_mapped_objects(self):
    """Import objects' mappings"""
    for converter in self.block_converters:
      converter.import_mapped_objects()

  def import_secondary_objects(self):
    """Import object which need to be imported after all mappings and other
    objects"""
    for converter in self.block_converters:
      converter.handle_secondary_objects_data(
          field_list=self.secondary_objects)
      converter.import_secondary_objects(
          field_list=self.secondary_objects)


class ExportConverter(BaseConverter):
  """Export Converter.

  This class contains and handles all block converters and makes sure that
  blocks and columns are handled in the correct order.
  """

  def initialize_block_converters(self):
    """Generate block converters.

    Generate block converters from a list of tuples with an object name and
    ids and store it to an instance variable.
    """
    object_map = {o.__name__: o for o in self.exportable.values()}
    for object_data in self.ids_by_type:
      class_name = object_data["object_name"]
      object_class = object_map[class_name]
      object_ids = object_data.get("ids", [])
      fields = object_data.get("fields")
      if class_name == "Snapshot":
        self.block_converters.append(
            SnapshotBlockConverter(self, object_ids, fields=fields)
        )
      else:
        block_converter = BlockConverter(self, object_class=object_class,
                                         fields=fields, object_ids=object_ids,
                                         class_name=class_name)
        block_converter.check_block_restrictions()
        self.block_converters.append(block_converter)

  def export_csv_data(self):
    """Export csv data."""
    with benchmark("Initialize block converters."):
      self.initialize_block_converters()
    with benchmark("Build csv data."):
      return self.build_csv_from_row_data()

  def build_csv_from_row_data(self):
    """Export each block separated by empty lines."""
    table_width = max([converter.block_width
                       for converter in self.block_converters])
    table_width += 1  # One line for 'Object line' column

    csv_string_builder = CsvStringBuilder(table_width)
    for block_converter in self.block_converters:
      csv_header = block_converter.generate_csv_header()
      csv_header[0].insert(0, "Object type")
      csv_header[1].insert(0, block_converter.name)

      csv_string_builder.append_line(csv_header[0])
      csv_string_builder.append_line(csv_header[1])

      for line in block_converter.generate_row_data():
        line.insert(0, "")
        csv_string_builder.append_line(line)

      csv_string_builder.append_line([])
      csv_string_builder.append_line([])

    return csv_string_builder.get_csv_string()
