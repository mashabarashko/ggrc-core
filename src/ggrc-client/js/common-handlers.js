/*
    Copyright (C) 2018 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import Spinner from 'spin.js';

let $body = $('body');
let $window = $(window);

// We remove loading class
$window.on('load', function () {
  $('html').removeClass('no-js');
});

$body.on("click", ".lhn-no-init", function() {
  $(this).removeClass('lhn-no-init');
  import(/* webpackChunkName: "lhn" */'./controllers/lhn_controllers')
    .then(function () {
      $("#lhn").cms_controllers_lhn();
      $(document.body).ggrc_controllers_recently_viewed();
    });
});

$body.on("click", "a[data-toggle=unmap]", function(ev) {
  let $el = $(this)
  ;
  //  Prevent toggling `openclose` state in trees
  ev.stopPropagation();
  $el.fadeTo('fast', 0.25);
  $el.children(".result").each(function(i, result_el) {
    let $result_el = $(result_el)
      , result = $result_el.data('result')
      , mappings = result && result.get_mappings();

    function notify(instance){
      $(document.body).trigger(
        "ajax:flash"
        , {"success" : "Unmap successful."}
      );
    }

    can.each(mappings, function(mapping) {
      mapping.refresh().done(function() {
        if (mapping instanceof CMS.Models.Control) {
          mapping.removeAttr('directive');
          mapping.save().then(notify);
        }
        else {
          mapping.destroy().then(notify);
        }
      });
    });
  });
});

// Initialize delegated event handlers
jQuery(function ($) {
  window.natural_comparator = function (a, b) {
    let i;
    a = a.slug.toString();
    b = b.slug.toString();
    if (a === b) {
      return 0;
    }

    a = a.replace(/(?=\D\d)(.)|(?=\d\D)(.)/g, '$1$2|').split('|');
    b = b.replace(/(?=\D\d)(.)|(?=\d\D)(.)/g, '$1$2|').split('|');

    for (i = 0; i < Math.max(a.length, b.length); i++) {
      if (Number(a[i]) === Number(a[i]) && Number(b[i]) === Number(b[i])) {
        if (Number(a[i]) < Number(b[i])) {
          return -1;
        }
        if (Number(b[i]) < Number(a[i])) {
          return 1;
        }
      } else {
        if (a[i] < b[i]) {
          return -1;
        }
        if (b[i] < a[i]) {
          return 1;
        }
      }
    }
    return 0;
  };

  // Turn the arrow when tree node content is shown
  $body.on('click', '[data-toggle="collapse"]', function (e) {
    let $this = $(this);
    let $expander_container = $this.closest(':has(.expander, .enddot)');
    let $expander = $expander_container.find('.expander').eq(0);
    let $target = $($this.data('target'));

    setTimeout(function () {
      if ($target.hasClass('in')) {
        $expander.addClass('in');
      } else {
        $expander.removeClass('in');
      }
    }, 100);
  });

  // After the modal template has loaded from the server, but before the
  //  data has loaded to populate into the body, show a spinner
  $body.on('loaded', '.modal.modal-slim, .modal.modal-wide', function (e) {
    let spin = function () {
      $(this).html(
        $(new Spinner().spin().el)
          .css({
            width: '100px', height: '100px',
            left: '50%', top: '50%',
            zIndex: calculate_spinner_z_index
          })
      ).one('loaded', function () {
        $(this).find('.source').each(spin);
      });
    };

    $(e.target).find('.modal-body .source').each(spin);
  });

  $body.on('click', '[data-toggle="list-remove"]', function (e) {
    e.preventDefault();
    $(this).closest('li').remove();
  });

  $body.on('click', '[data-toggle="list-select"]', function (e) {
    let $this;
    let $li;
    let target;
    let data;

    e.preventDefault();

    $this = $(this);
    $li = $this.closest('li');
    target = $li.closest('ul').data('list-target');

    if (target) {
      data = $.extend({}, $this.data('context') || {}, $this.data());
      $(target).tmpl_mergeitems([data]);
    }
  });

  $body.on('click', '[data-toggle="nested-dropdown"]', function (e) {
    let $parent = $(this).parent();
    let isActive = $parent.hasClass('open');
    if (!isActive) {
      $parent.toggleClass('open');
    }
    e.stopPropagation();
    e.preventDefault();
  });

  $('html').on('click.dropdown.data-api', function (e) {
    $('[data-toggle="nested-dropdown"]').parent().removeClass('open');
  });
});

jQuery(function ($) {
  function refresh_page() {
    setTimeout(can.proxy(window.location.reload, window.location), 10);
  }

  $body.on('ajax:complete', '[data-ajax-complete="refresh"]', refresh_page);
});

jQuery(function ($) {
  // Used in object_list sidebars (References, People, Categories)
  $body.on('modal:success', '.js-list-container-title a', function (e, data) {
    let $this = $(this);
    let $title = $this.closest('.js-list-container-title');
    let $span = $title.find('span');
    let $expander = $title.find('.expander').eq(0);

    $span.text('(' + (data.length || 0) + ')');

    if (data.length > 0) {
      $span.removeClass('no-object');
    } else {
      $span.addClass('no-object');
    }

    if (!$expander.hasClass('in')) {
      $expander.click();
    }
  });
});

jQuery(function ($) {
  function checkActive(notification_configs) {
    let inputs = $('.notify-wrap').find('input');
    let active_notifications = $.map(notification_configs, function (a) {
      if (a.enable_flag) {
        return a.notif_type;
      }
    });
    $.map(inputs, function (input) {
      // Handle the default case, in case notification objects are not set:
      if (notification_configs.length === 0) {
        input.checked = input.value === 'Email_Digest';
      } else {
        input.checked = active_notifications.indexOf(input.value) > -1;
      }
    });
  }
  function updateNotifications() {
    CMS.Models.NotificationConfig.findActive().then(checkActive);
    $body.off('click', '.user-dropdown > .dropdown-toggle', updateNotifications);
  }

  $body.on('click', '.user-dropdown > .dropdown-toggle', updateNotifications);

  // Don't close the dropdown if clicked on checkbox
  $body.on('click', '.notify-wrap', function (ev) {
    ev.stopPropagation();
  });

  $body.on('click', 'input[name=notifications]', function (ev, el) {
    let li = $(ev.target).closest('.notify-wrap');
    let inputs = li.find('input');
    let active = [];
    let email_now = li.find('input[value="Email_Now"]');
    let email_now_label = email_now.closest('label');
    let email_digest = li.find('input[value="Email_Digest"]');

    if (email_digest[0].checked) {
      email_now_label.removeClass('disabled');
      email_now.prop('disabled', false);
    } else if (!email_digest[0].checked) {// uncheck email_now
      email_now.prop('checked', false);
      email_now_label.addClass('disabled');
    }

    inputs.prop('disabled', true);
    active = $.map(inputs, function (input) {
      if (input.checked) {
        return input.value;
      }
    });
    CMS.Models.NotificationConfig.setActive(active).always(function (response) {
      email_digest.prop('disabled', false);
      if (email_digest[0].checked) {
        email_now.prop('disabled', false);
      }
    });
  });

  $body.on('click', '.clear-display-settings', function (e) {
    CMS.Models.DisplayPrefs.findAll().done(function (data) {
      let destroys = [];
      can.each(data, function (d) {
        d.unbind('change'); // forget about listening to changes.  we're going to refresh the page
        destroys.push(d.resetPagePrefs());
      });
      $.when.apply($, destroys).done(function () {
        GGRC.navigate();
      });
    });
  })
  .on('click', '.set-display-settings-default', function (e) {
    let page_token = getPageToken();
    CMS.Models.DisplayPrefs.findAll().done(function (data) {
      let destroys = [];
      can.each(data, function (d) {
        d.unbind('change'); // forget about listening to changes.  we're going to refresh the page
        destroys.push(d.setPageAsDefault(page_token));
      });
      $.when.apply($, destroys).done(function () {
        $body.trigger(
          'ajax:flash',
          {success: 'Saved page layout as default for ' + (page_token === 'dashboard' ? 'dashboard' : page_token)}
        );
      });
    });
  });
});

// Make all external links open in new window.
jQuery(function ($) {
  $body.on('click', 'a[href]:not([target])', function (e) {
    if (!e.isDefaultPrevented()) {
      if (/^http/.test(this.protocol) && this.hostname !== window.location.hostname) {
        e.preventDefault();
        window.open(this.href);
      }
    }
  });
});

jQuery(function ($) {
  // Footer expander animation helper
  function expander(toggle, direction) {
    let $this = $(toggle);
    let $expander = $this.closest('div').find('.section-expander');
    let out = direction === 'out';
    let height = $expander.outerHeight();
    let width = $expander.outerWidth();
    let start = out ? 0 : width;
    let end = out ? width : 0;
    let duration = 500;
    let clip;

    if (out) {
      $this.filter(':not(.section-sticky)').fadeOut(200);
    }

    // Check for intermediate animation
    // Update the starting point and duration as appropriate
    if ($expander.is(':animated')) {
      $expander.stop();
      clip = $expander.css('clip').match(/^rect\(([0-9.-]+)px,?\s+([0-9.-]+)px,?\s+([0-9.-]+)px,?\s+([0-9.-]+)px\)$/);
      if (clip) {
        // Start or end is always zero, so we can use some shortcuts
        start = parseFloat(clip[2]);
        duration = ~~((end ? end - start : start) / width * duration);
      }
    }

    // Process animation
    $expander.css({
      display: 'inline-block',
      marginRight: end + 'px',
      clip: 'rect(0px, ' + start + 'px, ' + height + 'px, 0px)',
      left: $this.is('.section-sticky') ? $this.outerWidth() : 0
    }).animate({
      marginRight: start + 'px'
    }, {
      duration: duration,
      easing: 'easeInOutExpo',
      step: function (now, fx) {
        $(this).css('clip', 'rect(0px, ' + (width - now + (out ? start : end)) + 'px, ' + height + 'px, 0px)');
      },
      complete: function () {
        if (!out) {
          $this.filter(':not(.section-sticky)').fadeIn();
          $(this).hide();
        }
        $(this).css({
          marginRight: '0px',
          clip: 'auto'
        });
      }
    });

    // Queue the reverse on mouseout
    if (out) {
      $this.closest('li').one('mouseleave', function () {
        expander($this, 'in');
      });
    }
  }

  // Footer expander animations (verify that an expander exists)
  $body.on('mouseenter', '.section-add:has(+ .section-expander), .section-expander:visible:animated', function (e) {
    let $this = $(this);
    expander($this.hasClass('section-add') ? $this : $this.prev('.section-add'), 'out');
  });

  $body.on('click', '.show-long', function (e) {
    let $this = $(this);
    let $descField = $this.closest('.span12').find('.tree-description');
    $this.hide();
    $descField.removeClass('short');
  });

  // show/hide audit lead and firm
  $body.on('mouseover', '.ui-autocomplete li a', function (e) {
    let $this = $(this);
    $this.addClass('active');
    $this.closest('li').addClass('active');
  });
  $body.on('mouseleave', '.ui-autocomplete li a', function (e) {
    let $this = $(this);
    $this.removeClass('active');
    $this.closest('li').removeClass('active');
  });
});


$(function () {
  $('body').on(
    'click',
    '[data-toggle="user-roles-modal-selector"]',
    async function (ev) {
      let $this = $(this);
      let options = $this.data('modal-selector-options');
      let dataSet = can.extend({}, $this.data());
      let objectParams = $this.attr('data-object-params');
      const {
        getOptionSet,
        'default': userRolesModalSelector,
      } = await import(
        /* webpackChunkName: "userRoleModalSelector" */
        './controllers/contributions'
      );
      dataSet.params = objectParams && JSON.parse(
        objectParams.replace(/\\n/g, '\\n')
      );


      can.each($this.data(), function (v, k) {
        //  This is just a mapping of keys to underscored keys
        let newKey = k.replace(
          /[A-Z]/g,
          function (str) {
            return '_' + str.toLowerCase();
          }
        );

        dataSet[newKey] = v;
        //  If we changed the key at all, delete the original
        if (newKey !== k) {
          delete dataSet[k];
        }
      });

      if (typeof options === 'string') {
        options = getOptionSet(options, dataSet);
      }

      ev.preventDefault();
      ev.stopPropagation();

      // Trigger the controller
      userRolesModalSelector.launch($this, options)
        .on('relationshipcreated relationshipdestroyed', function (ev, data) {
          // $this.trigger("modal:" + ev.type, data);
        });
    });
});

function openMapperByElement(ev, disableMapper) {
  let btn = $(ev.currentTarget);
  let data = {};

  can.each(btn.data(), function (val, key) {
    data[can.camelCaseToUnderscore(key)] = val;
  });

  if (data.tooltip) {
    data.tooltip.hide();
  }

  if (!data.clickable) {
    ev.preventDefault();
  }

  import(/*webpackChunkName: "mapper"*/ './controllers/mapper/mapper').then(mapper => {
    mapper.ObjectMapper.openMapper(data, disableMapper, btn);
  });
}

$body.on('openMapper', (el, ev, disableMapper) => {
  openMapperByElement(ev, disableMapper);
});

$body.on('click', ['unified-mapper', 'unified-search']
  .map(val => '[data-toggle="' + val + '"]').join(', '), (ev, disable) => {
  openMapperByElement(ev, disable);
});
