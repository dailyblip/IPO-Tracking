-- Distinguish common-equivalent conversion quantities from issued common shares.
-- No access policies, saved reports or valuation rules change.
alter table research.ownership_components
 drop constraint ownership_components_instrument_check,
 add constraint ownership_components_instrument_check
 check (instrument in ('common_share','rsu','option','warrant','preferred_conversion'));
