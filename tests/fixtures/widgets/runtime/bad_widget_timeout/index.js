'use strict';

// Never resolves → harness timeout → WGR-meta error.
module.exports = {
  init: function () {
    return new Promise(function () { /* intentional hang */ });
  },
};
