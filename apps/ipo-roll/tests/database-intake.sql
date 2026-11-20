-- Administrative staging test; no retained fixtures.
begin;
create temporary table test_payload(payload jsonb);
insert into test_payload values(jsonb_build_object(
  'id','20000000-0000-4000-8000-000000000001',
  'run_id','20000000-0000-4000-8000-000000000002',
  'version','legacy-intake/1','source_path','docs/data/filings.json',
  'source_commit',repeat('e',40),'input_sha256',repeat('e',64),'payload_sha256',repeat('f',64),
  'records',jsonb_build_array(jsonb_build_object(
    'id','20000000-0000-4000-8000-000000000003','ordinal',0,
    'pointer','/filings/0','record_sha256',repeat('d',64),'status','quarantined',
    'values',jsonb_build_object('company','Example'),
    'observations',jsonb_build_array(jsonb_build_object('field','company','value','Example','pointer','/filings/0/company','verification','feed_reported')),
    'holders','[]'::jsonb,
    'findings','["ROOT_LINEAGE_UNVERIFIED","SOURCE_DOCUMENT_CAPTURE_REQUIRED","COMMERCIAL_RIGHTS_REVIEW_REQUIRED","OPERATING_COMPANY_REVIEW_REQUIRED"]'::jsonb
  ))
));
do $$ declare p jsonb; result jsonb; before_count bigint; begin
  select payload into p from test_payload;
  select count(*) into before_count from research.offerings;
  result := ops.import_legacy_intake(p);
  if (result->>'inserted')::boolean is not true then raise exception 'First import was not inserted'; end if;
  result := ops.import_legacy_intake(p);
  if (result->>'inserted')::boolean is not false then raise exception 'Replay was not a no-op'; end if;
  if (select count(*) from ops.field_observations where record_id='20000000-0000-4000-8000-000000000003') <> 1 then raise exception 'Observation count wrong'; end if;
  if (select count(*) from ops.quality_findings where run_id='20000000-0000-4000-8000-000000000002') <> 4 then raise exception 'Replay duplicated findings'; end if;
  if (select count(*) from research.offerings) <> before_count then raise exception 'Import changed customer research'; end if;
  begin
    perform ops.import_legacy_intake(jsonb_set(p,'{payload_sha256}',to_jsonb(repeat('a',64))));
    raise exception 'Expected immutable conflict' using errcode='ZX001';
  exception when raise_exception then
    if sqlerrm <> 'Immutable batch conflict' then raise; end if;
  end;
  begin
    update ops.intake_records set candidate_values='{}' where id='20000000-0000-4000-8000-000000000003';
    raise exception 'Mutation was accepted' using errcode='ZX001';
  exception when sqlstate '55000' then null; end;
  begin
    delete from ops.intake_batches where id='20000000-0000-4000-8000-000000000001';
    raise exception 'Deletion was accepted' using errcode='ZX001';
  exception when sqlstate '55000' then null; end;
  -- A malformed later observation must roll back the entire function, including the batch.
  p := jsonb_set(p,'{id}','"20000000-0000-4000-8000-000000000004"');
  p := jsonb_set(p,'{version}', '"legacy-intake/1"');
  p := jsonb_set(p,'{run_id}','"20000000-0000-4000-8000-000000000005"');
  p := jsonb_set(p,'{input_sha256}',to_jsonb(repeat('b',64)));
  p := jsonb_set(p,'{records,0,id}','"20000000-0000-4000-8000-000000000006"');
  p := jsonb_set(p,'{records,0,observations,0,value}','"Wrong value"');
  begin
    perform ops.import_legacy_intake(p);
    raise exception 'Invalid observation accepted' using errcode='ZX001';
  exception when raise_exception then
    if sqlerrm <> 'Observation does not match candidate' then raise; end if;
  end;
  if exists(select 1 from ops.intake_batches where id='20000000-0000-4000-8000-000000000004') then raise exception 'Partial batch survived'; end if;
  if exists(select 1 from ops.ingestion_runs where id='20000000-0000-4000-8000-000000000005') then raise exception 'Partial run survived'; end if;
end $$;
set local role authenticated;
do $$ begin
  begin perform count(*) from ops.intake_batches; raise exception 'Customer can read intake' using errcode='ZX001'; exception when insufficient_privilege then null; end;
  begin perform ops.import_legacy_intake('{}'); raise exception 'Customer can run import' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
set local role anon;
do $$ begin
  begin perform count(*) from ops.holder_candidates; raise exception 'Anon can read holders' using errcode='ZX001'; exception when insufficient_privilege then null; end;
  begin perform ops.import_legacy_intake('{}'); raise exception 'Anon can run import' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'PASS: intake replay, conflict, immutability, atomic rollback, customer isolation' as result;
rollback;
