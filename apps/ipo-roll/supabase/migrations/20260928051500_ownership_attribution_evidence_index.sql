-- Cover the attribution evidence foreign key used by policy/source checks.
create index ownership_attributions_evidence on research.ownership_attributions(evidence_id);
