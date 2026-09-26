begin;
do $$ begin
  if not exists(select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='ops' and c.relname='sec_review_packets' and c.relrowsecurity) then raise exception 'Missing review RLS'; end if;
  begin update ops.sec_artifacts set raw_bytes=raw_bytes; raise exception 'Mutable artifacts' using errcode='ZX001'; exception when sqlstate '55000' then null; end;
  begin update ops.sec_review_packets set packet=packet; raise exception 'Mutable packet' using errcode='ZX001'; exception when sqlstate '55000' then null; end;
end $$;
set local role authenticated;
do $$ begin
 begin perform count(*) from ops.sec_artifacts; raise exception 'Source archive exposed' using errcode='ZX001'; exception when insufficient_privilege then null; end;
 begin perform count(*) from ops.sec_review_packets; raise exception 'Review exposed' using errcode='ZX001'; exception when insufficient_privilege then null; end;
 begin insert into ops.sec_artifacts values(repeat('f',64),1,decode('00','hex')); raise exception 'Customer write permitted' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
set local role anon;
do $$ begin
 begin perform count(*) from ops.sec_review_packets; raise exception 'Anonymous review access' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'PASS: SEC source immutability and customer/anonymous denial' result;
rollback;
