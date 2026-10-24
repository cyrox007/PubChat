import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
    isValidRegistrationHandle,
    isValidOptionalRegistrationEmail,
    parseHandleAvailability,
} from '../src/utils/registrationValidation.js';

// Regression: double-escaped \\s and \\. in an inline Vue regex rejected valid mail.
for (const valid of ['', ' ', 'name@example.com', 'first.last+test@gmail.com', 'a@sub.example.co.uk', '  User@Example.org  ']) {
    assert.equal(isValidOptionalRegistrationEmail(valid), true, `Should accept: ${valid}`);
}
for (const invalid of ['name@example', 'nameexample.com', 'a@@example.com', 'a b@example.com', 'a@b..', 'x'.repeat(255) + '@example.com']) {
    assert.equal(isValidOptionalRegistrationEmail(invalid), false, `Should reject: ${invalid}`);
}
for (const valid of ['abc', 'alex_123', 'test.name']) {
    assert.equal(isValidRegistrationHandle(valid), true, `Valid handle: ${valid}`);
}
for (const invalid of ['', 'ab', 'with space', 'имя', 'a'.repeat(33)]) {
    assert.equal(isValidRegistrationHandle(invalid), false, `Invalid handle: ${invalid}`);
}

assert.equal(parseHandleAvailability({ available: true }), 'available');
assert.equal(parseHandleAvailability({ available: false }), 'taken');
for (const invalid of [null, {}, { available: 'true' }, { isUnique: true }, { error: 'unavailable' }]) {
    assert.equal(parseHandleAvailability(invalid), 'unverified');
}

// Vue watch() eagerly executes its source getter at setup. Before this fix,
// the watch accessed the TDZ of `const form`, breaking registration on mount.
const component = readFileSync(new URL('../src/views/RegistrationView.vue', import.meta.url), 'utf8');
const formDeclaration = component.indexOf('const form = reactive(');
const watchDeclaration = component.indexOf('watch(() => form.handle,');
assert.ok(formDeclaration >= 0 && watchDeclaration > formDeclaration,
    'Registration form must be constructed before the username watch reads it');
assert.match(component, /isValidOptionalRegistrationEmail\(form\.email\)/,
    'Registration must use the tested email validator');
assert.match(component, /isValidRegistrationHandle\(value\)/,
    'Username preflight must use the tested handle validator');
assert.match(component, /handleRequestController\?\.abort\(\)/,
    'Changing usernames must cancel pending requests');
assert.match(component, /handleAvailability\.value = parseHandleAvailability\(response\.data\)/,
    'Availability must be derived from the Identity v2 contract');

const auth = readFileSync(new URL('../src/API/AuthService.js', import.meta.url), 'utf8');
assert.match(auth, /\$api\.get\('\/identity\/v2\/handle-availability',\s*\{\s*params:\s*\{\s*handle\s*\},\s*signal\s*\}\)/,
    'Username check must use the cancellable Identity v2 endpoint');

const backend = readFileSync(new URL('../../backend/views/identity/routers.py', import.meta.url), 'utf8');
assert.match(backend, /@router\.get\("\/handle-availability"\)/,
    'Identity v2 backend must expose the availability endpoint');
assert.match(backend, /@router\.post\("\/email-availability"\)/,
    'Identity v2 must provide a rate-limited email availability endpoint');
assert.match(backend, /check_email_budget\(request\)/,
    'Email preflight must enforce rate-limiting before credential lookup');
assert.match(component, /AuthService\.emailAvailability\(raw\.trim\(\), controller\.signal\)/,
    'Email preflight must use the cancellable Identity v2 endpoint');
assert.match(component, /emailAvailability\.value !== 'taken'/,
    'Known registered emails must disable submit');
assert.match(component, /<Transition name="field-feedback">\s*<span :key="emailHint\.key"/,
    'Email feedback must crossfade instead of deferring new hints behind out-in leaving');
assert.ok(component.includes('.field-feedback-slot > span { grid-area: 1 / 1;'),
    'Outgoing and incoming field hints must overlap without a layout jump');
assert.match(component, /prefers-reduced-motion: reduce/,
    'Hint animations must honor OS reduced-motion accessibility settings');
assert.match(auth, /\$api\.post\('\/identity\/v2\/email-availability', \{ email \}, \{ signal \}\)/,
    'Email check must POST body, not leak email into URL query params');

console.log('Registration email, username, component initialization and API regression checks passed.');
