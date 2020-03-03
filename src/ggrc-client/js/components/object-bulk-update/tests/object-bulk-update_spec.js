/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import makeArray from 'can-util/js/make-array/make-array';
import canMap from 'can-map';
import Component from '../object-bulk-update';
import * as stateUtils from '../../../plugins/utils/state-utils';
import tracker from '../../../tracker';

describe('object-bulk-update component', () => {
  let events;

  beforeAll(() => {
    events = Component.prototype.events;
  });

  describe('viewModel() method', () => {
    let parentViewModel;
    let method;
    let targetStates;
    let result;

    beforeEach(() => {
      parentViewModel = new canMap();
      method = Component.prototype.viewModel;
      targetStates = ['Assigned', 'In Progress'];

      spyOn(stateUtils, 'getBulkStatesForModel')
        .and.returnValue(targetStates);

      result = method({type: 'some type'}, parentViewModel)();
    });

    it('returns correct type', () => {
      expect(result.type).toEqual('some type');
    });

    it('returns correct target states', () => {
      let actual = makeArray(result.targetStates);
      expect(actual).toEqual(targetStates);
    });

    it('returns correct target state', () => {
      expect(result.targetState).toEqual('Assigned');
    });

    it('returns set reduceToOwnedItems flag', () => {
      expect(result.reduceToOwnedItems).toBeTruthy();
    });

    it('returns set showTargetState flag', () => {
      expect(result.showTargetState).toBeTruthy();
    });

    it('returns correct defaultSort', () => {
      expect(result.defaultSort.serialize()[0].key).toEqual('task due date');
    });
  });

  describe('closeModal event', function () {
    let event;
    let element;

    beforeAll(function () {
      let scope;
      element = {
        trigger: jasmine.createSpy(),
      };
      element.find = jasmine.createSpy().and.returnValue(element);
      scope = {
        element: element,
      };

      event = events.closeModal.bind(scope);
    });

    it('closes modal if element defined', function () {
      event();

      expect(element.trigger).toHaveBeenCalledWith('click');
    });
  });

  describe('.btn-cancel click event', function () {
    it('closes modal', function () {
      let context = {
        closeModal: jasmine.createSpy(),
      };
      let event = events['.btn-cancel click'].bind(context);

      event();

      expect(context.closeModal).toHaveBeenCalled();
    });
  });

  describe('.btn-update click event', function () {
    let event;
    let context;

    beforeEach(function () {
      context = {
        viewModel: new canMap(),
      };
      event = events['.btn-update click'].bind(context);

      spyOn(tracker, 'start').and.returnValue(() => {});
    });

    it('invokes update callback', function () {
      context.viewModel.callback = jasmine.createSpy()
        .and.returnValue({
          then() {},
        });
      context.viewModel.selected = [1];
      context.viewModel.targetState = 'In Progress';

      event();

      expect(context.viewModel.callback)
        .toHaveBeenCalled();
    });
  });

  describe('"inserted" event handler', function () {
    let event;
    let context;

    beforeEach(function () {
      context = {
        viewModel: new canMap({
          onSubmit: jasmine.createSpy(),
        }),
      };
      event = events.inserted.bind(context);
    });

    it('calls onSubmit()', function () {
      event();

      expect(context.viewModel.onSubmit).toHaveBeenCalled();
    });
  });
});
