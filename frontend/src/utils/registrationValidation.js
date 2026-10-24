/**
 * Browser-safe validation shared by the registration form and CI regression tests.
 * This is only a format/preflight check; Identity v2 remains authoritative.
 */
export const isValidRegistrationHandle = (value) =>
    typeof value === 'string' && /^[A-Za-z0-9_.]{3,32}$/.test(value.trim());

export const isValidOptionalRegistrationEmail = (value) => {
    if (typeof value !== 'string') return false;
    const email = value.trim();
    if (email === '') return true;
    if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return false;
    const [local, domain] = email.split('@');
    // Catch common malformed domains and local parts before the backend's EmailStr check.
    return !local.startsWith('.') && !local.endsWith('.') && !local.includes('..') &&
        !domain.startsWith('.') && !domain.endsWith('.') && !domain.includes('..');
};

/** Identity v2 responds with { available: boolean }. Unknown shapes fail closed. */
export const parseHandleAvailability = (data) => {
    if (data?.available === true) return 'available';
    if (data?.available === false) return 'taken';
    return 'unverified';
};
