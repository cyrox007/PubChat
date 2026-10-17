import crypto from 'node:crypto';
import {
  createVerificationQrMatrix,
  createVerificationQrSvg,
  matchesVerificationQrPayload,
  verificationQrPayload,
} from '../src/crypto/verificationQr.js';

const safety = '12345 67890 12345 67890 12345 67890 12345 67890';
const payload = verificationQrPayload(safety);
if (payload !== 'pubchat-e2ee-v1:1234567890123456789012345678901234567890') {
  throw new Error('Unexpected verification QR payload');
}
if (!matchesVerificationQrPayload(payload, safety)) throw new Error('Expected QR payload to match');
if (matchesVerificationQrPayload('pubchat-e2ee-v1:0000000000000000000000000000000000000000', safety)) {
  throw new Error('Mismatched QR payload accepted');
}
if (matchesVerificationQrPayload('{"safety_number":"1234567890123456789012345678901234567890"}', safety)) {
  throw new Error('Unversioned QR payload accepted');
}

const matrix = createVerificationQrMatrix(safety);
if (matrix.length !== 33 || matrix.some((row) => row.length !== 33)) throw new Error('QR must be version 4 (33x33)');
if (matrix.some((row) => row.some((value) => typeof value !== 'boolean'))) throw new Error('QR contains unresolved modules');
const bits = matrix.flat().map((value) => value ? '1' : '0').join('');
const digest = crypto.createHash('sha256').update(bits).digest('hex');
if (digest !== 'a6048d11a4dde47d4ecdb34cb4af414d1c398a54bc13b4e79bc1cd4367d87acc') {
  throw new Error(`QR matrix regression: ${digest}`);
}

const svg = createVerificationQrSvg(safety);
if (!svg.startsWith('<svg') || !svg.includes('<path') || svg.includes('http://') && !svg.includes('http://www.w3.org/2000/svg')) {
  throw new Error('Unexpected QR SVG output');
}
if (/https?:\/\/(?!www\.w3\.org\/2000\/svg)/.test(svg)) throw new Error('QR SVG must not load external resources');

for (const invalid of ['', '1234', 'a'.repeat(40), '1'.repeat(41)]) {
  let rejected = false;
  try { verificationQrPayload(invalid); } catch { rejected = true; }
  if (!rejected) throw new Error(`Invalid safety number accepted: ${invalid}`);
}

console.log('E2EE verification QR checks passed');
