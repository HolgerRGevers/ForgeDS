'use strict';

// Declares only get_pending_claims but also invokes approve_claim → WGR001 error.
module.exports = {
  init: async function () {
    await ZOHO.CREATOR.API.invokeCustomApi('get_pending_claims', {});
    await ZOHO.CREATOR.API.invokeCustomApi('approve_claim', { claim_id: 2 });
  },
};
