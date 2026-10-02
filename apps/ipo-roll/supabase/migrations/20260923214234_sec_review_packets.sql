-- Private source objects and selected review passages. No customer publication.
create table ops.sec_artifacts (
  sha256 text primary key check (sha256 ~ '^[0-9a-f]{64}$'),
  raw_bytes integer not null check (raw_bytes > 0 and raw_bytes <= 20000000),
  content_gzip bytea not null check (octet_length(content_gzip) > 0),
  created_at timestamptz not null default now()
);
create table ops.sec_review_packets (
  id uuid primary key,
  intake_record_id uuid not null references ops.intake_records,
  packet_sha256 text unique not null check (packet_sha256 ~ '^[0-9a-f]{64}$'),
  packet jsonb not null check ((jsonb_typeof(packet)='object'
    and packet->>'version'='sec-selected-review/1'
    and packet->>'rights_status'='unreviewed'
    and packet->'publication_allowed'='false'::jsonb
    and jsonb_typeof(packet->'people')='array') is true),
  created_at timestamptz not null default now()
);
create index sec_review_intake on ops.sec_review_packets(intake_record_id);
create table ops.sec_packet_artifacts (
  packet_id uuid not null references ops.sec_review_packets,
  artifact_sha256 text not null references ops.sec_artifacts,
  primary key(packet_id,artifact_sha256)
);
create index sec_packet_artifact_lookup on ops.sec_packet_artifacts(artifact_sha256);
do $$ declare t text; begin
  foreach t in array array['sec_artifacts','sec_review_packets','sec_packet_artifacts'] loop
    execute format('alter table ops.%I enable row level security',t);
    execute format('revoke all on ops.%I from public,anon,authenticated',t);
    execute format('create trigger immutable_sec_evidence before update or delete on ops.%I for each row execute function ops.reject_intake_mutation()',t);
  end loop;
end $$;
