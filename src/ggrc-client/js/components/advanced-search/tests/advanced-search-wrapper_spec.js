/*
  Copyright (C) 2018 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Component from '../advanced-search-wrapper';

describe('GGRC.Components.advancedSearchWrapper', function () {
  'use strict';

  var viewModel;
  var events;
  beforeEach(() => {
    viewModel = new Component.prototype.viewModel();
    events = Component.prototype.events;
  });

  describe('"{viewModel} modelName" handler', function () {
    var that;
    var handler;
    beforeEach(function () {
      that = {
        viewModel: viewModel,
      };
      handler = events['{viewModel} modelName'];
    });

    it('calls resetFilters() method', function () {
      spyOn(viewModel, 'resetFilters');
      handler.call(that);
      expect(viewModel.resetFilters).toHaveBeenCalled();
    });
  });
});
