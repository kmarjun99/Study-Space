import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { transformSync } from 'esbuild';

const root = path.resolve(import.meta.dirname, '..');
const source = fs.readFileSync(path.join(root, 'src/utils/renewalDisplay.ts'), 'utf8');
const compiled = transformSync(source, {
  loader: 'ts',
  format: 'cjs',
  platform: 'node',
}).code;

const loadModule = () => {
  const module = { exports: {} };
  vm.runInNewContext(compiled, {
    module,
    exports: module.exports,
    require: () => ({}),
    Date,
    Intl,
  });
  return module.exports;
};

test('renewal display prioritizes pending payments', () => {
  const renewal = loadModule();
  const display = renewal.getRenewalDisplay({ renewalStatus: 'ACTIVE', paymentStatus: 'PENDING' });
  assert.equal(display.label, 'Payment Pending');
  assert.equal(display.variant, 'warning');
  assert.equal(display.needsAttention, true);
});

test('renewal due and expired are attention states', () => {
  const renewal = loadModule();
  assert.equal(renewal.getRenewalDisplay({ renewalStatus: 'RENEWAL_DUE' }).label, 'Renewal Due');
  assert.equal(renewal.getRenewalDisplay({ renewalStatus: 'EXPIRED' }).variant, 'error');
  assert.equal(renewal.getRenewalDisplay({ renewalStatus: 'ACTIVE' }).needsAttention, false);
});

test('formats renewal window dates safely', () => {
  const renewal = loadModule();
  assert.equal(renewal.formatRenewalWindow(undefined, '2026-02-05'), '—');
  assert.match(renewal.formatRenewalWindow('2026-02-01', '2026-02-05'), /01 Feb 2026 - 05 Feb 2026/);
});
