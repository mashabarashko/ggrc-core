/*
 Copyright (C) 2018 Google Inc., authors, and contributors
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import {
  buildModifiedACL,
  buildModifiedListField,
  buildModifiedAttValues,
  getInstanceView,
} from '../../plugins/utils/object-history-utils';

import template from './templates/review-proposal.mustache';
const tag = 'review-proposal';

export default can.Component.extend({
  tag,
  template,
  viewModel: {
    define: {
      buttonView: {
        get() {
          return `${GGRC.mustache_path}/modals/review_proposal.mustache`;
        },
      },
      canReview: {
        get() {
          return this.attr('proposal.status') !== 'applied';
        },
      },
    },
    leftRevisionId: null,
    rightRevision: null,
    proposal: {},
    instance: {},
    isLoading: false,
    modalTitle: 'Review: Compare to Current',
    prepareComparerConfig() {
      const instance = this.attr('instance');
      const leftRevisionId = this.attr('leftRevisionId');
      const rightRevision = this.attr('rightRevision');
      let query;

      this.attr('isLoading', true);

      // build isntance view
      instance.attr('view', getInstanceView(instance));

      if (leftRevisionId && rightRevision) {
        this.attr('isLoading', false);

        // revisions are already ready
        this.openRevisionComparer();
        return;
      }

      query = {
        __sort: '-updated_at',
        __page: 1,
        __page_size: 1,
        resource_type: instance.attr('type'),
        resource_id: instance.attr('id'),
      };

      // get last revision
      CMS.Models.Revision.findAll(query).then((data) => {
        const originalRevision = data[0];
        this.attr('leftRevisionId', originalRevision.id);
        this.buildModifiedRevision(originalRevision);
      });
    },
    buildModifiedRevision(originalRevision) {
      const diff = this.attr('proposal.content');
      const diffAttributes = diff.custom_attribute_values;
      const rightRevision = new can.Map({
        id: originalRevision.id,
        content: Object.assign({}, originalRevision.content.attr()),
      });

      const modifiedContent = rightRevision.content;

      this.applyFields(modifiedContent, diff.fields);
      this.applyFields(modifiedContent, diff.mapping_fields);
      this.applyAcl(modifiedContent, diff.access_control_list);
      this.applyListFields(modifiedContent, diff.mapping_list_fields);
      this.applyCustomAttributes(modifiedContent, diffAttributes);

      this.attr('rightRevision', rightRevision);
      this.attr('isLoading', false);
      this.openRevisionComparer();
    },
    applyFields(instance, modifiedFields) {
      const fieldNames = can.Map.keys(modifiedFields);

      fieldNames.forEach((fieldName) => {
        const modifiedField = modifiedFields[fieldName];
        instance[fieldName] = modifiedField;
      });
    },
    applyAcl(instance, modifiedRoles) {
      const modifiedACL = buildModifiedACL(instance, modifiedRoles);
      instance.access_control_list = modifiedACL;
    },
    applyListFields(instance, modifiedFields) {
      const fieldNames = can.Map.keys(modifiedFields);
      fieldNames.forEach((fieldName) => {
        const items = instance[fieldName];
        const modifiedItems = modifiedFields[fieldName];
        const modifiedField = buildModifiedListField(items, modifiedItems);
        instance[fieldName] = modifiedField;
      });
    },
    applyCustomAttributes(instance, modifiedAttributes) {
      const values = instance
        .custom_attribute_values
        .attr()
        .map((val) => {
          // mark as stub
          val.isStub = true;
          return val;
        });

      const definitions = instance
        .custom_attribute_definitions
        .attr();

      const modifiedValues =
        buildModifiedAttValues(values, definitions, modifiedAttributes);

      instance.custom_attribute_values = modifiedValues;
      instance.custom_attributes = modifiedValues;
    },
    openRevisionComparer() {
      const el = this.attr('$el');
      const revisionsComparer = el.find('revisions-comparer');
      if (revisionsComparer && revisionsComparer.viewModel) {
        revisionsComparer.viewModel().compareIt();
      }
    },
  },
  events: {
    inserted() {
      this.viewModel.attr('$el', this.element);
    },
  },
});
