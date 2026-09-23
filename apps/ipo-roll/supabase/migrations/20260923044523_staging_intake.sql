-- Private, append-only intake. No publication path and no customer access.
create table ops.intake_batches (
  id uuid primary key,
  run_id uuid not null references ops.ingestion_runs,
  importer_version text not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  payload jsonb not null,
  record_count integer not null check (record_count > 0),
  created_at timestamptz not null default now(),
  unique (run_id, importer_version)
);
create table ops.intake_records (
  id uuid primary key,
  batch_id uuid not null references ops.intake_batches,
  ordinal integer not null check (ordinal >= 0),
  source_pointer text not null,
  source_record_sha256 text not null check (source_record_sha256 ~ '^[0-9a-f]{64}$'),
  candidate_values jsonb not null check (jsonb_typeof(candidate_values) = 'object'),
  status text not null default 'quarantined' check (status = 'quarantined'),
  unique (batch_id, ordinal)
);
create table ops.field_observations (
  record_id uuid not null references ops.intake_records,
  field_name text not null check (field_name in ('company','ticker','cik','accession_no','form','filed','filing_date','stage','pricing_date','offering_price','value','filing_price','primary_offering_shares','secondary_offering_shares')),
  observed_value jsonb not null,
  source_pointer text not null,
  reported_source jsonb,
  verification text not null default 'feed_reported' check (verification = 'feed_reported'),
  primary key (record_id, field_name)
);
create table ops.holder_candidates (
  record_id uuid not null references ops.intake_records,
  ordinal integer not null check (ordinal >= 0),
  source_pointer text not null,
  candidate_values jsonb not null check (jsonb_typeof(candidate_values) = 'object'),
  reported_source jsonb,
  verification text not null default 'unverified' check (verification = 'unverified'),
  primary key (record_id, ordinal)
);
create function ops.reject_intake_mutation() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  raise exception 'Intake history is append-only; create a new version instead' using errcode = '55000';
end $$;
revoke all on function ops.reject_intake_mutation() from public, anon, authenticated;
do $$ declare t text; begin
  foreach t in array array['intake_batches','intake_records','field_observations','holder_candidates'] loop
    execute format('alter table ops.%I enable row level security', t);
    execute format('revoke all on ops.%I from public, anon, authenticated', t);
    execute format('create trigger immutable_intake before update or delete on ops.%I for each row execute function ops.reject_intake_mutation()', t);
  end loop;
end $$;

create function ops.import_legacy_intake(p jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare
  batch_id uuid := (p->>'id')::uuid;
  run_id uuid := (p->>'run_id')::uuid;
  prior jsonb;
  r jsonb;
  o jsonb;
  h jsonb;
  code text;
  rid uuid;
  n integer;
begin
  if p->>'version' is distinct from 'legacy-intake/1'
     or p->>'source_path' is distinct from 'docs/data/filings.json'
     or coalesce(p->>'source_commit','') !~ '^[0-9a-f]{40}$'
     or coalesce(p->>'input_sha256','') !~ '^[0-9a-f]{64}$'
     or coalesce(p->>'payload_sha256','') !~ '^[0-9a-f]{64}$'
     or jsonb_typeof(p->'records') is distinct from 'array' then
    raise exception 'Unsupported intake contract';
  end if;
  n := jsonb_array_length(p->'records');
  if n < 1 or n > 10000 then raise exception 'Invalid intake size'; end if;
  -- Serialize retries of the same immutable snapshot.
  perform pg_advisory_xact_lock(hashtextextended(batch_id::text, 0));
  select payload into prior from ops.intake_batches where id = batch_id;
  if found then
    if prior is distinct from p then raise exception 'Immutable batch conflict'; end if;
    return jsonb_build_object('batch_id',batch_id,'inserted',false,'records',n,'published',0);
  end if;
  insert into ops.ingestion_runs(id,source_commit,input_sha256,engine_version,status,finished_at)
    values(run_id,p->>'source_commit',p->>'input_sha256','legacy@'||(p->>'source_commit'),'quarantined',now())
    on conflict (source_commit,input_sha256) do nothing;
  if not exists(select 1 from ops.ingestion_runs ir where ir.id=run_id and ir.source_commit=p->>'source_commit' and ir.input_sha256=p->>'input_sha256') then
    raise exception 'Run identity conflict';
  end if;
  insert into ops.intake_batches(id,run_id,importer_version,payload_sha256,payload,record_count)
    values(batch_id,run_id,p->>'version',p->>'payload_sha256',p,n);
  for r in select value from jsonb_array_elements(p->'records') loop
    rid := (r->>'id')::uuid;
    if r->>'status' is distinct from 'quarantined'
       or jsonb_typeof(r->'observations') is distinct from 'array'
       or jsonb_typeof(r->'holders') is distinct from 'array'
       or jsonb_typeof(r->'findings') is distinct from 'array'
       or jsonb_typeof(r->'values') is distinct from 'object'
       or not (r->'findings' @> '["ROOT_LINEAGE_UNVERIFIED","SOURCE_DOCUMENT_CAPTURE_REQUIRED","COMMERCIAL_RIGHTS_REVIEW_REQUIRED","OPERATING_COMPANY_REVIEW_REQUIRED"]'::jsonb)
       or (r->'values')::text ~* 'stanford|#8c1515' then
      raise exception 'Invalid quarantined record';
    end if;
    if exists(select 1 from jsonb_object_keys(r->'values') k where k <> all(array['company','ticker','cik','accession_no','form','filed','filing_date','stage','pricing_date','offering_price','value','filing_price','primary_offering_shares','secondary_offering_shares'])) then
      raise exception 'Field not permitted in commercial intake';
    end if;
    insert into ops.intake_records(id,batch_id,ordinal,source_pointer,source_record_sha256,candidate_values)
      values(rid,batch_id,(r->>'ordinal')::integer,r->>'pointer',r->>'record_sha256',r->'values');
    for o in select value from jsonb_array_elements(r->'observations') loop
      if o->>'verification' is distinct from 'feed_reported'
         or not ((r->'values') ? (o->>'field'))
         or (o->'value') is distinct from (r->'values'->(o->>'field')) then
        raise exception 'Observation does not match candidate';
      end if;
      insert into ops.field_observations(record_id,field_name,observed_value,source_pointer,reported_source)
        values(rid,o->>'field',o->'value',o->>'pointer',nullif(o->'reported_source','null'::jsonb));
    end loop;
    if (select count(*) from ops.field_observations where record_id=rid) <> (select count(*) from jsonb_object_keys(r->'values')) then
      raise exception 'Incomplete field provenance';
    end if;
    for h in select value from jsonb_array_elements(r->'holders') loop
      if h->>'verification' is distinct from 'unverified'
         or jsonb_typeof(h->'values') is distinct from 'object'
         or (h->'values')::text ~* 'stanford|#8c1515' then
        raise exception 'Invalid holder candidate';
      end if;
      if exists(select 1 from jsonb_object_keys(h->'values') k where k <> all(array['name','holder_type','is_beneficial_owner','ownership_percent','ownership_percent_before','ownership_percent_after','shares_before_ipo','shares_sold_ipo','shares_after_ipo'])) then
        raise exception 'Holder field not permitted';
      end if;
      insert into ops.holder_candidates(record_id,ordinal,source_pointer,candidate_values,reported_source)
        values(rid,(h->>'ordinal')::integer,h->>'pointer',h->'values',nullif(h->'reported_source','null'::jsonb));
    end loop;
    for code in select jsonb_array_elements_text(r->'findings') loop
      if code !~ '^[A-Z_]+$' then raise exception 'Invalid finding code'; end if;
      insert into ops.quality_findings(run_id,record_key,rule_code,reason)
        values(run_id,batch_id::text||':'||(r->>'ordinal'),code,'Unverified legacy intake: '||code);
    end loop;
  end loop;
  return jsonb_build_object('batch_id',batch_id,'inserted',true,'records',n,'published',0);
end $$;
revoke all on function ops.import_legacy_intake(jsonb) from public,anon,authenticated;
comment on function ops.import_legacy_intake(jsonb) is 'Administrative staging intake only. Does not write research or evidence tables, approve rights, or publish a release.';
