import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hypotheticalValue, boundaryAtDate } from '../shared/liquidity-scenario.js';

test('hypothetical value keeps cent precision without floating point or unsafe integer rounding', () => {
  assert.equal(hypotheticalValue('3', '0.10'), '0.30');
  assert.equal(hypotheticalValue('1200000', '19'), '22,800,000.00');
  assert.equal(hypotheticalValue('999999999999', '999999999.99'), '999,999,999,989,000,000,000.01');
  assert.equal(hypotheticalValue('0', '0.00'), '0.00');
});
test('hypothetical value refuses incomplete, negative, fractional-share, exponential and out of bounds inputs', () => {
  for (const quantity of ['', '-1', '1.2', '1e6', 'NaN', '1000000000000']) assert.equal(hypotheticalValue(quantity, '10'), null);
  for (const price of ['', '-1', '1.001', '1e6', 'Infinity', '1000000000', ' 1']) assert.equal(hypotheticalValue('1', price), null);
});
test('scenario dates compare calendar boundaries only, accepting equality and rejecting rolled-over dates', () => {
  assert.equal(boundaryAtDate('2026-09-27', '2026-09-26'), 'ahead');
  assert.equal(boundaryAtDate('2026-09-27', '2026-09-27'), 'reached');
  assert.equal(boundaryAtDate('2026-09-27', '2027-01-01'), 'reached');
  assert.equal(boundaryAtDate('2028-02-29', '2028-03-01'), 'reached');
  for (const value of ['2026-02-29', '2026-04-31', '2026-9-27', '', 'unknown']) {
    assert.equal(boundaryAtDate(value, '2026-09-27'), null);
    assert.equal(boundaryAtDate('2026-09-27', value), null);
  }
});
