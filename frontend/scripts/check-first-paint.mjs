import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const entry = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');

assert.doesNotMatch(
  html,
  /<link\s+rel=["']stylesheet["'][^>]*cdnjs\.cloudflare\.com/i,
  'Third-party icon CSS must not block document first paint',
);
assert.match(entry, /const loadOptionalIconStyles = \(\) =>/,
  'Optional icon stylesheet must have a loader');
assert.match(entry, /document\.head\.appendChild\(link\)/,
  'Third-party CSS is installed only after main JS is executing');
assert.match(entry, /loadOptionalIconStyles\(\);[\s\S]*await store\.dispatch\('initializeUser'\)/,
  'Icon loading must not be awaited by authenticated startup');
console.log('First paint: optional third-party stylesheet is non-blocking');
