import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/calls/useWebRtcCall.js', import.meta.url), 'utf8');
const overlay = readFileSync(new URL('../src/components/Calls/CallOverlay.vue', import.meta.url), 'utf8');

const fail = (message) => {
  console.error(`Call security guard failed: ${message}`);
  process.exitCode = 1;
};

if (!source.includes("CryptoService.accountDevices(state.peerUid)")) {
  fail('call setup must pass through the common peer device-directory continuity boundary');
}
if (!source.includes("e2ee_directory_transparency_conflict")) {
  fail('call setup must map transparency conflicts to an explicit security failure');
}
if (!source.includes("security_unavailable")) {
  fail('incoming security failure must decline with an explicit allow-listed reason');
}
if (!source.includes("transport-encrypted-unverified")) {
  fail('call state must retain an explicit unverified transport-encryption claim');
}
if (source.includes("verifiedApplicationE2ee: true") || source.includes("deviceIdentityBound: true")) {
  fail('client must not hard-code verified E2EE/device identity binding');
}

const startBody = source.slice(source.indexOf('const start = async'), source.indexOf('const accept = async'));
if (startBody.indexOf('await checkPeerDirectoryContinuity()') < 0 || startBody.indexOf('await acquireMedia') < 0) {
  fail('outgoing call must check peer directory continuity and acquire media explicitly');
} else if (startBody.indexOf('await checkPeerDirectoryContinuity()') > startBody.indexOf('await acquireMedia')) {
  fail('outgoing security check must happen before camera/microphone capture');
}

const acceptBody = source.slice(source.indexOf('const accept = async'), source.indexOf('const decline ='));
if (acceptBody.indexOf('await checkPeerDirectoryContinuity()') < 0 || acceptBody.indexOf('await acquireMedia') < 0) {
  fail('incoming call must check peer directory continuity and acquire media explicitly');
} else if (acceptBody.indexOf('await checkPeerDirectoryContinuity()') > acceptBody.indexOf('await acquireMedia')) {
  fail('incoming security check must happen before camera/microphone capture');
}

if (!overlay.includes('Не verified E2EE') || !overlay.includes('DTLS fingerprint ещё не привязан')) {
  fail('call UI must communicate the application-level identity/E2EE limitation');
}

if (process.exitCode) process.exit(process.exitCode);
console.log('Call security checks passed');
