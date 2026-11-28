// Deliberately independent of source facts and saved reports. No quote lookup,
// automatic position selection, saleability classification or report mutation.
export function hypotheticalValue(quantity: string, price: string): string | null {
  if (!/^\d{1,12}$/.test(quantity) || !/^\d{1,9}(?:\.\d{1,2})?$/.test(price)) return null;
  const [whole, fraction = ''] = price.split('.');
  const cents = BigInt(quantity) * (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0')));
  return `${(cents / 100n).toLocaleString('en-US')}.${(cents % 100n).toString().padStart(2, '0')}`;
}

export function boundaryAtDate(boundary: string, date: string): 'reached' | 'ahead' | null {
  for (const value of [boundary, date]) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    const parsed = new Date(`${value}T00:00:00Z`);
    if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return null;
  }
  return boundary <= date ? 'reached' : 'ahead';
}
