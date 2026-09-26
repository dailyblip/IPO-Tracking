import test from 'node:test';
import assert from 'node:assert/strict';
import { valueHolding, type Holding, type HoldingQuote } from '../shared/holdings.js';
const source = {title:'Synthetic filing',url:'https://example.test/filing',date:'2026-01-01',excerpt:'100 direct common shares',locator:'Table'};
const h: Holding = {id:'h',issuerId:'i',securityId:'A',shareClass:'A',shares:100,basis:'current',asOf:'2026-01-01',ownership:'direct',personalEconomicInterestConfirmed:true,reconciliationConfirmed:true,reconciledThrough:'2026-01-02T17:00:00Z',reviewed:true,instrument:'common',footnotes:[],source,restrictions:'Restricted; valuation does not establish saleability.'};
const q: HoldingQuote = {issuerId:'i',securityId:'A',price:12.5,currency:'USD',asOf:'2026-01-02T16:00:00Z',kind:'last-known',verified:true,source};
test('supported estimate retains quote and never represents cash proceeds',()=>{const v=valueHolding(h,q);assert.equal(v.amount,1250);assert.equal(v.quote?.asOf,q.asOf);assert.match(v.reason,/not cash proceeds/)});
test('unsafe holdings never valued',()=>{for(const delta of [{basis:'projected-post-offering'},{personalEconomicInterestConfirmed:false},{reconciliationConfirmed:false},{reconciledThrough:'2026-01-01'},{reviewed:false},{instrument:'option'},{shares:-1}])assert.equal(valueHolding({...h,...delta} as Holding,q).amount,null)});
test('missing, mismatched, future or unverified prices never valued',()=>{assert.equal(valueHolding(h).amount,null);for(const delta of [{verified:false},{issuerId:'other'},{securityId:'B'},{price:0},{price:NaN},{asOf:'2099-01-01'},{asOf:'2025-01-01'},{asOf:'bad'},{currency:''}])assert.equal(valueHolding(h,{...q,...delta}).amount,null)});
