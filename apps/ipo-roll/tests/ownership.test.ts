import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ownershipRows, type OwnershipPosition } from '../shared/ownership.js';
const source = { title:'Synthetic filing',url:null,date:'2026-09-01',excerpt:'Synthetic evidence',locator:'1' };
const position: OwnershipPosition = { id:'p',shareClass:'Common shares and underlying awards',reportedTotal:150,
  quantityKind:'beneficial_total',positionBasis:'pre',holdingsAsOf:'2026-08-01',filingDate:'2026-09-01',
  source,conditions:'Conditional restrictions',explanation:'',assessmentDate:null,evidence:[],
  components:{status:'reconciled',items:[
    {ordinal:1,instrument:'common_share',quantity:100,attribution:'trust_or_family',description:'Trust shares',source},
    {ordinal:2,instrument:'option',quantity:50,attribution:'unknown',description:'Option interests',source}]}};
test('ownership grid replaces aggregate with components without double counting or inferring economics',()=>{
  const rows=ownershipRows([position]);
  assert.equal(rows.length,2);
  assert.equal(rows.reduce((n,r)=>n+(r.quantity||0),0),150);
  assert.equal(rows[0].attribution,'Trust / family attribution');
  assert.equal(rows[1].security,'Option underlying shares');
  assert.equal(rows[1].attribution,'Attribution unconfirmed');
});
test('incomplete evidence keeps a labeled aggregate; classes and alternative bases remain separate',()=>{
  const rows=ownershipRows([{...position,components:{status:'incomplete',items:[]}},
    {...position,id:'b',quantityKind:'reported_shares',shareClass:'Class B common stock',positionBasis:'post'}]);
  assert.equal(rows.length,2);
  assert.equal(rows[0].attribution,'Breakdown incomplete · includes awards');
  assert.equal(rows[1].security,'Class B common stock');
  assert.equal(rows[1].position.positionBasis,'post');
  assert.deepEqual(ownershipRows([]),[]);
});
