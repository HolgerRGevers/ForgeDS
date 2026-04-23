'use strict';

// Declares both APIs but only calls one → WGR001 warning for approve_claim.
module.exports = {
  init: async function () {
    await ZOHO.CREATOR.API.invokeCustomApi('get_pending_claims', {});
  },
};
