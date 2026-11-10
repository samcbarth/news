// The Quillmark site config. Fill these in when the accounts exist; empty means "render nothing".
window.QM_CONFIG = {
  // Google AdSense publisher id, e.g. 'ca-pub-1234567890123456'. Empty = no ad slots render.
  ADSENSE_CLIENT: '',
  // Optional AdSense ad-unit ids per slot name. Missing ids fall back to auto ads in that slot.
  ADSENSE_SLOTS: {
    'after-lead': '',
    'between-rails-1': '',
    'between-rails-2': '',
    'sidebar': '',
    'in-article': '',
    'end-of-article': '',
    'section-mid': '',
    'section-end': ''
  },
  // Not used on the hub (no affiliate links here); kept for parity with the network config.
  AMAZON_TAG: '',
  // Contact page: HubSpot form (portal 20693956) if FORM_ID is set, otherwise a mailto link if CONTACT_EMAIL is set.
  HUBSPOT_PORTAL_ID: '20693956',
  HUBSPOT_FORM_ID: '9f5020df-cf22-4018-bac9-4a89f544e208',
  HUBSPOT_REGION: 'na1',
  CONTACT_EMAIL: ''
};
