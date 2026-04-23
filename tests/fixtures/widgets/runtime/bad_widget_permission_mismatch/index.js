'use strict';

// Invokes addRecords (requires ZOHO.CREATOR.API.write) but manifest only
// declares ZOHO.CREATOR.API.read → WGR004 error.
// consumes_apis 'approve_claim' is honoured so WGR001 does not also fire.
module.exports = {
  init: async function () {
    await ZOHO.CREATOR.API.invokeCustomApi('approve_claim', { claim_id: 3 });
    await ZOHO.CREATOR.API.addRecords('expense_claims', { amount: 10 });
  },
};
