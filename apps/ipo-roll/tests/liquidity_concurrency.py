"""Emit reproducible two-session staging QA SQL; no credentials or source payloads.

For each CASE, execute setup (commits disposable users), start first and second
concurrently on independent connections, verify, and ALWAYS cleanup. The first
holds its account row lock 20s; second must overlap (observe pg_locks/activity).
Use authenticated SQL roles with synthetic JWT claims, not browser credentials.
Cases: subject (RPC/direct), account (RPC/direct across subjects), replay (RPC/RPC),
stale (competing explicit refreshes), repeatable (stale snapshot fails 40001).
Admin setup briefly disables the two report triggers in its own transaction to
seed boundary counts; it changes no existing account/report. Never use production.
"""
import argparse

CASES = ['subject', 'account', 'replay', 'stale', 'repeatable']

def sql(case, phase):
    number = CASES.index(case) + 1
    uid = f'65000000-0000-4000-8000-{number:012d}'
    claims = f'''set local role authenticated;
select set_config('request.jwt.claims','{{"sub":"{uid}","role":"authenticated"}}',true);'''
    subjects = '''select distinct r.offering_id,r.person_id from research.roles r
where evidence.source_json(r.evidence_id) is not null order by r.offering_id,r.person_id limit 11'''
    if phase == 'setup':
        return f'''begin;
insert into auth.users(id,email) values('{uid}','liquidity-concurrency-{case}@example.invalid');
insert into app.entitlements(user_id,active) values('{uid}',true);
insert into app.reviewers(user_id) values('{uid}');
create temporary table quota_subjects as {subjects};
do $$ begin if (select count(*) from quota_subjects)<>11 then raise exception 'Missing 11 test subjects'; end if; end $$;
alter table app.liquidity_reports disable trigger liquidity_report_quota;
alter table app.liquidity_reports disable trigger liquidity_report_snapshot;
insert into app.liquidity_reports(user_id,offering_id,person_id,request_id,report)
select '{uid}',s.offering_id,s.person_id,gen_random_uuid(),'{{"syntheticQuotaFixture":true}}'::jsonb
from (select * from quota_subjects order by offering_id,person_id limit {11 if case=='account' else 1}) s cross join generate_series(1,9);
alter table app.liquidity_reports enable trigger liquidity_report_snapshot;
alter table app.liquidity_reports enable trigger liquidity_report_quota;
insert into app.liquidity_report_accounts(user_id) values('{uid}');
commit;
select 'Fixture ready: {case}' result;'''
    if phase in ('first', 'second'):
        second = phase == 'second'
        prefix = f"begin isolation level {'repeatable read' if second and case=='repeatable' else 'read committed'};\nset local statement_timeout='40s';\nset local application_name='ipo-roll-quota-{case}-{phase}';\n{claims}\n"
        if not second:
            prefix += "select app.lock_liquidity_report_account();\n"
        if second:
            # A sequential transport is not a passing concurrency test. Admin
            # NOWAIT must observe the first connection holding the mutex row.
            overlap = f"""reset role;
do $$ begin
 begin
  perform 1 from app.liquidity_report_accounts where user_id='{uid}' for update nowait;
  raise exception 'No overlapping account lock observed' using errcode='ZX001';
 exception when lock_not_available then null; end;
end $$;
{claims}
"""
            prefix += overlap
        # Capture subject and original previous version before waiting on account lock.
        prefix += f'''create temporary table quota_target as select offering_id,person_id,id previous_id
from app.liquidity_reports where user_id=auth.uid()
order by offering_id,person_id,created_at desc,id desc offset {9 if second and case=='account' else 0} limit 1;
'''
        request = "'65000000-ffff-4000-8000-000000000001'::uuid" if case == 'replay' else 'gen_random_uuid()'
        write = f'''perform public.ipo_roll_request_liquidity(s.offering_id,s.person_id,{request},s.previous_id);'''
        if second and case in ('subject','account','repeatable'):
            write = '''insert into app.liquidity_reports(offering_id,person_id,request_id)
values(s.offering_id,s.person_id,gen_random_uuid());'''
        if second and case in ('subject','account','repeatable'):
            expected = 'serialization_failure' if case=='repeatable' else 'program_limit_exceeded'
            body = f'''begin {write}
raise exception 'Concurrent request unexpectedly exceeded boundary' using errcode='ZX001';
exception when {expected} then null; end;'''
        else:
            body = write
        return prefix+f'''do $$ declare s record; begin select * into strict s from quota_target; {body} end $$;
{'' if second else 'select pg_sleep(20);'}
commit;
select 'PASS: {case} {phase}' result;'''
    if phase == 'verify':
        expected = 100 if case=='account' else 10
        return f'''do $$ begin
if (select count(*) from app.liquidity_reports where user_id='{uid}')<>{expected} then
raise exception 'Wrong final concurrent count'; end if;
if (select count(*) from app.liquidity_reports where user_id='{uid}' and not(report ? 'syntheticQuotaFixture'))<>1 then
raise exception 'Concurrent request generated more than one snapshot'; end if;
end $$;
select 'PASS: {case}, exactly one new snapshot' result;'''
    if phase == 'cleanup':
        return f'''begin;
delete from auth.users where id='{uid}' and email='liquidity-concurrency-{case}@example.invalid';
commit;
select count(*) remaining_fixture_accounts from auth.users where id='{uid}';'''
    if phase == 'observe':
        return f'''select application_name,wait_event_type,wait_event from pg_stat_activity
where application_name like 'ipo-roll-quota-{case}-%';'''
    raise ValueError(phase)

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('case',choices=CASES)
    p.add_argument('phase',choices=['setup','first','second','verify','cleanup','observe'])
    a=p.parse_args()
    print(sql(a.case,a.phase))
