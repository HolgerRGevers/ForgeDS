/* Good widget fixture — should pass ESLint. */
ZOHO.embeddedApp.on('PageLoad', function (data) {
  ZOHO.CREATOR.API.invokeApi('get_pending_claims', { page: 1 });
});
ZOHO.embeddedApp.init();
