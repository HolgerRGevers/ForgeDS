'use strict';

module.exports = {
  init: async function () {
    await ZOHO.CREATOR.API.invokeCustomApi('get_pending_claims', {});
    await ZOHO.CREATOR.API.invokeCustomApi('approve_claim', { claim_id: 1 });
  },
};
