-- Shared reviewed claims are never customer-authored. No existing facts qualify
-- automatically, and no saved private report is updated by this migration.
create table research.historical_value_reviews (
 id uuid primary key default gen_random_uuid(),
 kind text not null check(kind in ('holding','completed_sale')),
 offering_id uuid not null references research.offerings(id),
 party_id uuid not null references research.parties(id),
 ownership_id uuid not null references research.ownerships(id),
 component_ordinal int,
 quantity numeric not null check(quantity>=0 and quantity=trunc(quantity) and quantity<=9007199254740991),
 holdings_date date not null,
 position_basis text not null check(position_basis in ('actual_disclosed','projected_post_offering','completed_holder_sale')),
 holder_kind text not null check(holder_kind in ('person','organization','trust')),
 attribution text not null check(attribution in ('personal_economic','reported_organization','reported_trust')),
 source_security_id text not null check(length(btrim(source_security_id)) between 1 and 200),
 source_share_class text not null check(length(btrim(source_share_class)) between 1 and 200),
 price_security_id text not null check(length(btrim(price_security_id)) between 1 and 200),
 price_share_class text not null check(length(btrim(price_share_class)) between 1 and 200),
 price numeric(20,8) not null check(price>0),
 currency text not null check(currency~'^[A-Z]{3}$'),
 price_date date not null,
 compatibility_method text not null check(compatibility_method in ('same_security','reviewed_common_share_conversion')),
 conversion_numerator bigint not null default 1 check(conversion_numerator between 1 and 9007199254740991),
 conversion_denominator bigint not null default 1 check(conversion_denominator between 1 and 9007199254740991),
 reconciled_through date not null,
 exposure_id text not null check(length(btrim(exposure_id)) between 1 and 200),
 projection_conditions text not null default '',
 completed_sale_confirmed boolean not null default false,
 sale_price_confirmed boolean not null default false,
 quantity_evidence_id uuid not null references evidence.spans(id),
 holder_evidence_id uuid not null references evidence.spans(id),
 price_evidence_id uuid not null references evidence.spans(id),
 compatibility_evidence_id uuid not null references evidence.spans(id),
 overlap_evidence_id uuid not null references evidence.spans(id),
 source_hashes jsonb not null check(jsonb_typeof(source_hashes)='object'),
 reviewed_at timestamptz not null,
 approved boolean not null default false,
 foreign key(ownership_id,component_ordinal) references research.ownership_components(ownership_id,ordinal),
 check((kind='holding' and position_basis in ('actual_disclosed','projected_post_offering'))
   or (kind='completed_sale' and position_basis='completed_holder_sale' and component_ordinal is null)),
 check((holder_kind='person' and attribution='personal_economic')
   or (holder_kind='organization' and attribution='reported_organization')
   or (holder_kind='trust' and attribution='reported_trust')),
 check(position_basis<>'projected_post_offering' or length(btrim(projection_conditions))>0)
);
create index historical_value_reviews_subject on research.historical_value_reviews(offering_id,party_id);
create index historical_value_reviews_ownership on research.historical_value_reviews(ownership_id);
alter table research.historical_value_reviews enable row level security;
revoke all on research.historical_value_reviews from public,anon,authenticated;
grant select on research.historical_value_reviews to authenticated;

-- Invoker access to every underlying span/source is required. The hash map is
-- keyed by document ID and must match the current retained document exactly.
create function research.historical_evidence_json(p_span uuid,p_hashes jsonb,p_reviewed timestamptz)
returns jsonb language sql stable security invoker set search_path='' as $$
 select jsonb_build_object('documentId',d.id,'documentHash',d.content_sha256,
  'sourceVersion',d.id::text||':'||d.content_sha256,'filingAccession',f.accession,
  'filingDate',f.filed_on,'retrievedAt',to_char(d.retrieved_at at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'reviewedAt',to_char(p_reviewed at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'reviewStatus','reviewed','url',s.url,'locator',sp.locator,'excerpt',sp.excerpt)
 from evidence.spans sp join evidence.documents d on d.id=sp.document_id
 join evidence.sources s on s.id=d.source_id join research.filings f on f.id=s.filing_id
 where sp.id=p_span and evidence.source_json(sp.id) is not null
 and d.content_sha256~'^[0-9a-f]{64}$' and jsonb_typeof(p_hashes->d.id::text)='string'
 and p_hashes->>d.id::text=d.content_sha256
 and f.filed_on is not null and d.retrieved_at is not null and p_reviewed is not null
 and f.filed_on<=d.retrieved_at::date and d.retrieved_at<=p_reviewed
 and length(btrim(sp.excerpt))>0 and length(btrim(sp.locator))>0
$$;
revoke all on function research.historical_evidence_json(uuid,jsonb,timestamptz) from public,anon;
grant execute on function research.historical_evidence_json(uuid,jsonb,timestamptz) to authenticated;
create policy historical_value_review_read on research.historical_value_reviews for select to authenticated using(
 (select app.has_access()) and approved and reviewed_at<=now()
 and exists(select 1 from research.ownerships o where o.id=ownership_id and o.approved
  and o.offering_id=historical_value_reviews.offering_id and o.party_id=historical_value_reviews.party_id)
 and not exists(select 1 from unnest(array[quantity_evidence_id,holder_evidence_id,price_evidence_id,
   compatibility_evidence_id,overlap_evidence_id]) e
  where research.historical_evidence_json(e,source_hashes,reviewed_at) is null)
 and not exists(select 1 from jsonb_object_keys(source_hashes) k where not exists(
  select 1 from evidence.spans sp where sp.document_id::text=k and sp.id=any(array[
   quantity_evidence_id,holder_evidence_id,price_evidence_id,compatibility_evidence_id,overlap_evidence_id])))
);

-- Calculation occurs only while constructing a requested private report. Both
-- the exact SQL output and the frozen reviewed input/provenance are retained.
create function research.historical_value_snapshot(p_offering uuid,p_party uuid,p_asof timestamptz)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare c record; q jsonb; h jsonb; p jsonb; v jsonb; x jsonb; ev jsonb;
 inputs jsonb; output jsonb; context jsonb; reason text; scope text; label text;
 holdings jsonb:='[]'; sales jsonb:='[]'; priced_quantity numeric; amount text;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 if p_asof is null or p_asof>clock_timestamp() then raise invalid_parameter_value; end if;
 for c in
  select r.*,o.quantity_kind,o.shares parent_quantity,o.share_class parent_class,o.holdings_as_of,
   o.position_basis parent_basis,o.evidence_id parent_evidence,o.filing_id parent_filing,
   part.name holder_name,part.kind canonical_holder_kind,f.company_id,
   f.stage,f.final_price,f.pricing_date,f.currency offering_currency,f.source_id offering_source,
   co.quantity component_quantity,co.instrument component_instrument,co.evidence_id component_evidence,
   co.approved component_approved,co.attribution component_attribution,
   count(*) over(partition by r.kind,r.position_basis,r.exposure_id) exposure_count
  from research.historical_value_reviews r
  join research.ownerships o on o.id=r.ownership_id
  join research.offerings f on f.id=r.offering_id
  join research.parties part on part.id=r.party_id
  left join research.ownership_components co on co.ownership_id=r.ownership_id and co.ordinal=r.component_ordinal
  where r.offering_id=p_offering and r.party_id=p_party and r.approved
  order by r.kind,r.id
 loop
  reason:=null; amount:=null; priced_quantity:=null;
  q:=research.historical_evidence_json(c.quantity_evidence_id,c.source_hashes,c.reviewed_at);
  h:=research.historical_evidence_json(c.holder_evidence_id,c.source_hashes,c.reviewed_at);
  p:=research.historical_evidence_json(c.price_evidence_id,c.source_hashes,c.reviewed_at);
  v:=research.historical_evidence_json(c.compatibility_evidence_id,c.source_hashes,c.reviewed_at);
  x:=research.historical_evidence_json(c.overlap_evidence_id,c.source_hashes,c.reviewed_at);
  scope:=case when c.holder_kind='person' then 'personal_economic_holding' else 'reported_holder_holding' end;
  label:=case when c.kind='completed_sale' then 'Documented gross holder-sale proceeds'
   when c.position_basis='projected_post_offering' then 'Projected post-offering historical IPO-price estimate'
   else 'Historical IPO-price estimate' end;
  context:=jsonb_build_object('analysisAsOf',to_char(p_asof at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
   'currentSourceHashes',(select jsonb_object_agg(e->>'documentId',e->>'documentHash')
    from jsonb_array_elements(jsonb_build_array(q,h,p,v,x)) e where e->>'documentId' is not null));
  if q is null or h is null or p is null or v is null or x is null or c.reviewed_at>p_asof then reason:='invalid_evidence';
  elsif exists(select 1 from unnest(array[c.quantity_evidence_id,c.holder_evidence_id,c.price_evidence_id,c.compatibility_evidence_id,c.overlap_evidence_id]) e
   join evidence.spans sp on sp.id=e join evidence.documents doc on doc.id=sp.document_id
   join evidence.sources src on src.id=doc.source_id join research.filings filing on filing.id=src.filing_id
   where filing.company_id<>c.company_id) then reason:='identity_mismatch';
  elsif length(btrim(c.holder_name))=0 or (c.holder_kind='person' and c.canonical_holder_kind<>'person')
   or (c.holder_kind in ('organization','trust') and c.canonical_holder_kind<>'organization') then reason:='unsupported_holder_attribution';
  elsif c.exposure_count>1 then reason:='duplicate_exposure';
  elsif c.holdings_date>p_asof::date or c.price_date>p_asof::date
   or (q->>'filingDate')::date<c.holdings_date or (p->>'filingDate')::date<c.price_date then reason:='invalid_dates';
  elsif c.kind='holding' and (c.stage is distinct from 'Priced'
   or c.final_price is null or c.pricing_date is null or c.offering_currency is null
   or c.price is distinct from c.final_price or c.price_date is distinct from c.pricing_date or c.currency is distinct from c.offering_currency
   or not exists(select 1 from evidence.spans sp join evidence.documents doc on doc.id=sp.document_id
    where sp.id=c.price_evidence_id and doc.source_id=c.offering_source)) then reason:='non_final_price';
  elsif c.kind='holding' and (c.holdings_as_of is null or c.holdings_date<>c.holdings_as_of
   or c.source_share_class is distinct from c.parent_class
   or (c.parent_basis='pre' and c.position_basis<>'actual_disclosed')
   or (c.parent_basis='post' and c.position_basis<>'projected_post_offering')
   or c.parent_basis is null or c.parent_basis not in ('pre','post')) then reason:='identity_mismatch';
  elsif c.kind='holding' and c.component_ordinal is null and (c.quantity_kind<>'reported_shares'
   or c.quantity is distinct from c.parent_quantity or c.quantity_evidence_id<>c.parent_evidence) then reason:='aggregate_or_unknown_quantity';
  elsif c.kind='holding' and c.component_ordinal is not null and (c.quantity_kind<>'beneficial_total'
   or not coalesce(c.component_approved,false) or c.component_instrument<>'common_share'
   or c.quantity is distinct from c.component_quantity or c.quantity_evidence_id<>c.component_evidence
   or coalesce(research.ownership_components_json(c.ownership_id)->>'status','incomplete')<>'reconciled') then reason:='unsupported_instrument';
  elsif c.kind='holding' and c.component_ordinal is not null and
   (c.component_attribution='unknown' or (c.attribution='personal_economic' and c.component_attribution<>'direct')) then reason:='unsupported_holder_attribution';
  elsif c.kind='completed_sale' and not c.completed_sale_confirmed then reason:='sale_not_completed';
  elsif c.kind='completed_sale' and not c.sale_price_confirmed then reason:='sale_price_not_established';
  elsif c.kind='completed_sale' and (c.holdings_date<>c.price_date or c.compatibility_method<>'same_security') then reason:='invalid_dates';
  elsif c.compatibility_method='same_security' and (c.source_security_id<>c.price_security_id
   or c.source_share_class<>c.price_share_class or c.conversion_numerator<>1 or c.conversion_denominator<>1) then reason:='unsupported_conversion';
  elsif c.reconciled_through<greatest(c.holdings_date,c.price_date) or c.reconciled_through>p_asof::date
   or (v->>'filingDate')::date<c.reconciled_through then reason:='incomplete_reconciliation';
  elsif mod(c.quantity*c.conversion_numerator,c.conversion_denominator)<>0 then reason:='unsupported_conversion'; end if;
  if reason is null then
   priced_quantity:=div(c.quantity*c.conversion_numerator,c.conversion_denominator);
   amount:=(priced_quantity*c.price)::text;
  end if;
  h:=jsonb_build_object('id',c.party_id,'name',c.holder_name,'kind',c.holder_kind,
   'attribution',c.attribution,'evidence',jsonb_build_array(h));
  if c.kind='holding' then
   ev:=jsonb_build_array(q)||(h->'evidence');
   ev:=ev||jsonb_build_array(x,p,v);
   inputs:=jsonb_build_object('position',jsonb_build_object(
    'id',c.id,'issuerId',c.company_id,'offeringId',c.offering_id,'securityId',c.source_security_id,
    'shareClass',c.source_share_class,'holder',h,'instrument','common_share',
    'quantityKind','disaggregated_shares','shares',c.quantity,'basis',c.position_basis,'holdingsDate',c.holdings_date,
    'projectionConditions',c.projection_conditions,'evidence',jsonb_build_array(q),
    'overlap',jsonb_build_object('status','reviewed_distinct','exposureId',c.exposure_id,'evidence',jsonb_build_array(x))),
    'price',jsonb_build_object('issuerId',c.company_id,'offeringId',c.offering_id,'securityId',c.price_security_id,
     'shareClass',c.price_share_class,'kind','authoritative_final_ipo_price','price',c.price::text,
     'currency',c.currency,'pricingDate',c.price_date,'evidence',jsonb_build_array(p)),
    'compatibility',jsonb_build_object('status','reviewed_compatible','positionId',c.id,
     'fromSecurityId',c.source_security_id,'toSecurityId',c.price_security_id,'method',c.compatibility_method,
     'numerator',c.conversion_numerator,'denominator',c.conversion_denominator,
     'reconciledThrough',c.reconciled_through,'evidence',jsonb_build_array(v)));
  else
   ev:=jsonb_build_array(q)||(h->'evidence'); ev:=ev||jsonb_build_array(p);
   inputs:=jsonb_build_object('sale',jsonb_build_object('id',c.id,'issuerId',c.company_id,'offeringId',c.offering_id,
    'securityId',c.source_security_id,'shareClass',c.source_share_class,'holder',h,
    'kind',case when c.completed_sale_confirmed then 'completed_holder_sale' else 'unknown' end,
    'instrument','common_share','sharesSold',c.quantity,'saleDate',c.holdings_date,'evidence',jsonb_build_array(q),
    'price',jsonb_build_object('issuerId',c.company_id,'offeringId',c.offering_id,'securityId',c.price_security_id,
     'shareClass',c.price_share_class,'kind',case when c.sale_price_confirmed then 'documented_completed_holder_sale_price' else 'unknown' end,
     'holderId',c.party_id,'saleId',c.id,'saleDate',c.price_date,'amount',c.price::text,
     'currency',c.currency,'evidence',jsonb_build_array(p))));
  end if;
  output:=jsonb_build_object('status',case when reason is null then 'established' else 'unknown' end,
   'reason',reason,'method','reviewed-filing-historical-value/1','analysisAsOf',context->>'analysisAsOf',
   'positionId',c.id,'holderId',c.party_id,'valueScope',scope,'label',label,
   'grossAmount',amount,'currency',case when reason is null then c.currency else null end,
   'inputShares',c.quantity,'pricedShares',priced_quantity::text,'price',case when reason is null then c.price::text else null end,
   'holdingsDate',c.holdings_date,'priceDate',c.price_date,'positionBasis',c.position_basis,
   'conditions',nullif(c.projection_conditions,''),'evidence',ev,
   'limitations',case when c.kind='completed_sale' then jsonb_build_array(
    'Gross documented sale consideration; fees, taxes, net proceeds, and payment receipt are unknown.',
    'A fund or trust sale does not establish personal cash proceeds for a controller or beneficiary.')
    else jsonb_build_array('Historical filing-based estimate; not a current market quote or current personal wealth.',
     'Does not establish cash proceeds, transferable shares, or saleability. Restrictions may still apply.',
     'Fees, taxes, net proceeds, and market impact are unknown.') end);
  inputs:=inputs||jsonb_build_object('claimId',c.id,'ownershipId',c.ownership_id,'exposureId',c.exposure_id,'context',context,'output',output);
  if c.kind='holding' then holdings:=holdings||jsonb_build_array(inputs);
  else sales:=sales||jsonb_build_array(inputs); end if;
 end loop;
 return jsonb_build_object('version','historical-value-snapshot/1','calculator','reviewed-filing-historical-value/1',
  'asOf',to_char(p_asof at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'holdings',holdings,'sales',sales,
  'notice','Static historical calculations from explicitly reviewed claims. Missing claims are unknown. Alternative positions are not summed. Current market quotes remain unavailable.');
end $$;
revoke all on function research.historical_value_snapshot(uuid,uuid,timestamptz) from public,anon;
grant execute on function research.historical_value_snapshot(uuid,uuid,timestamptz) to authenticated;

create function app.append_historical_value_snapshot() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
 if new.user_id is distinct from auth.uid() or new.report->>'id' is distinct from new.id::text
  or new.report->>'personId' is distinct from new.person_id::text then raise insufficient_privilege; end if;
 new.report:=new.report||jsonb_build_object('historicalValues',
  research.historical_value_snapshot(new.offering_id,new.person_id,new.created_at));
 return new;
end $$;
revoke all on function app.append_historical_value_snapshot() from public,anon,authenticated;
-- PostgreSQL orders same-event triggers alphabetically: quota -> snapshot ->
-- snapshot_valuation. Existing locks, quotas, replay and explicit refresh remain.
create trigger liquidity_report_snapshot_valuation before insert on app.liquidity_reports
for each row execute function app.append_historical_value_snapshot();
