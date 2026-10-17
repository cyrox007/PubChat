import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const api = read('../src/API/CryptoService.js');
const checkpoint = read('../src/crypto/directoryCheckpoint.js');
const verification = read('../src/crypto/deviceVerification.js');

const fail = (message) => {
  console.error(`E2EE directory transparency guard failed: ${message}`);
  process.exitCode = 1;
};

if (!api.includes('assertDirectoryCheckpoint')) fail('peer device directory reads must validate checkpoints');
if (!api.includes('/directory-history')) fail('checkpoint advancement must have a history continuity endpoint');
if (!api.includes('historyLoader')) fail('accountDevices must validate forward hash-chain continuity');
if (!checkpoint.includes('checkpoint_rollback')) fail('rollback detection is missing');
if (!checkpoint.includes('checkpoint_fork')) fail('same-sequence fork detection is missing');
if (!checkpoint.includes('history_hash_chain_broken')) fail('history hash-chain break detection is missing');
if (!checkpoint.includes('MAX_HISTORY_GAP')) fail('history verification work must remain bounded');
if (checkpoint.includes("import CryptoService")) fail('checkpoint validator must not create an API import cycle');
if (!verification.includes('CryptoService.accountDevices')) fail('device verification must use the common checkpoint boundary');

if (process.exitCode) process.exit(process.exitCode);
console.log('E2EE directory transparency checks passed');
