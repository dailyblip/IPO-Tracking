-- A filing can repeat an entity-held quantity under a named person's SEC
-- beneficial-owner row without establishing either personal economics or the
-- person's control authority. Preserve that reported relationship without
-- duplicating the entity quantity.
alter table research.ownership_attributions
 drop constraint ownership_attributions_kind_check;
alter table research.ownership_attributions
 add constraint ownership_attributions_kind_check
 check(kind in ('beneficial_entitlement','control_authority','reported_beneficial_owner'));
