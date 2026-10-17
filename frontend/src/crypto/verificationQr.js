const VERSION = 4;
const SIZE = 33;
const DATA_CODEWORDS = 64;
const ECC_PER_BLOCK = 18;
const BLOCK_DATA = 32;
const PREFIX = 'pubchat-e2ee-v1:';

const exp = new Array(512).fill(0);
const log = new Array(256).fill(0);
let fieldValue = 1;
for (let i = 0; i < 255; i += 1) {
	exp[i] = fieldValue;
	log[fieldValue] = i;
	fieldValue <<= 1;
	if (fieldValue & 0x100) fieldValue ^= 0x11d;
}
for (let i = 255; i < 512; i += 1) exp[i] = exp[i - 255];

const gfMul = (a, b) => (!a || !b) ? 0 : exp[log[a] + log[b]];

const generatorPolynomial = (degree) => {
	let poly = [1];
	for (let i = 0; i < degree; i += 1) {
		const next = new Array(poly.length + 1).fill(0);
		for (let j = 0; j < poly.length; j += 1) {
			next[j] ^= poly[j];
			next[j + 1] ^= gfMul(poly[j], exp[i]);
		}
		poly = next;
	}
	return poly;
};

const rsRemainder = (data, degree) => {
	const generator = generatorPolynomial(degree);
	const remainder = new Array(degree).fill(0);
	for (const value of data) {
		const factor = value ^ remainder[0];
		remainder.shift();
		remainder.push(0);
		for (let j = 0; j < degree; j += 1) remainder[j] ^= gfMul(generator[j + 1], factor);
	}
	return remainder;
};

const appendBits = (bits, value, length) => {
	for (let i = length - 1; i >= 0; i -= 1) bits.push(((value >>> i) & 1) !== 0);
};

const encodeData = (payload) => {
	const bytes = Array.from(new TextEncoder().encode(payload));
	if (bytes.length > 62) throw new Error('verification_qr_payload_too_long');
	const bits = [];
	appendBits(bits, 0b0100, 4);
	appendBits(bits, bytes.length, 8);
	for (const byte of bytes) appendBits(bits, byte, 8);
	const capacity = DATA_CODEWORDS * 8;
	appendBits(bits, 0, Math.min(4, capacity - bits.length));
	while (bits.length % 8) bits.push(false);
	const out = [];
	for (let i = 0; i < bits.length; i += 8) {
		let byte = 0;
		for (let j = 0; j < 8; j += 1) byte = (byte << 1) | (bits[i + j] ? 1 : 0);
		out.push(byte);
	}
	let firstPad = true;
	while (out.length < DATA_CODEWORDS) {
		out.push(firstPad ? 0xec : 0x11);
		firstPad = !firstPad;
	}
	return out;
};

const interleave = (data) => {
	const blocks = [data.slice(0, BLOCK_DATA), data.slice(BLOCK_DATA)];
	const ecc = blocks.map((block) => rsRemainder(block, ECC_PER_BLOCK));
	const out = [];
	for (let i = 0; i < BLOCK_DATA; i += 1) for (const block of blocks) out.push(block[i]);
	for (let i = 0; i < ECC_PER_BLOCK; i += 1) for (const block of ecc) out.push(block[i]);
	return out;
};

const blankMatrix = () => Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
const setFunction = (matrix, row, col, value) => {
	if (row >= 0 && row < SIZE && col >= 0 && col < SIZE) matrix[row][col] = Boolean(value);
};

const drawFinder = (matrix, row, col) => {
	for (let dr = -1; dr <= 7; dr += 1) {
		for (let dc = -1; dc <= 7; dc += 1) {
			const r = row + dr;
			const c = col + dc;
			if (r < 0 || r >= SIZE || c < 0 || c >= SIZE) continue;
			const inside = dr >= 0 && dr <= 6 && dc >= 0 && dc <= 6;
			const dark = inside && (dr === 0 || dr === 6 || dc === 0 || dc === 6 || (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4));
			setFunction(matrix, r, c, dark);
		}
	}
};

const drawAlignment = (matrix, row, col) => {
	for (let dr = -2; dr <= 2; dr += 1) {
		for (let dc = -2; dc <= 2; dc += 1) {
			setFunction(matrix, row + dr, col + dc, Math.max(Math.abs(dr), Math.abs(dc)) !== 1);
		}
	}
};

const reserveFormat = (matrix) => {
	const positions = [];
	for (let i = 0; i <= 5; i += 1) positions.push([i, 8]);
	positions.push([7, 8], [8, 8], [8, 7]);
	for (let i = 9; i < 15; i += 1) positions.push([8, 14 - i]);
	for (let i = 0; i < 8; i += 1) positions.push([8, SIZE - 1 - i]);
	for (let i = 8; i < 15; i += 1) positions.push([SIZE - 15 + i, 8]);
	for (const [row, col] of positions) setFunction(matrix, row, col, false);
};

const buildBase = () => {
	const matrix = blankMatrix();
	drawFinder(matrix, 0, 0);
	drawFinder(matrix, 0, SIZE - 7);
	drawFinder(matrix, SIZE - 7, 0);
	drawAlignment(matrix, 26, 26);
	for (let i = 8; i < SIZE - 8; i += 1) {
		if (matrix[6][i] === null) setFunction(matrix, 6, i, i % 2 === 0);
		if (matrix[i][6] === null) setFunction(matrix, i, 6, i % 2 === 0);
	}
	reserveFormat(matrix);
	setFunction(matrix, 4 * VERSION + 9, 8, true);
	return matrix;
};

const maskBit = (mask, row, col) => {
	switch (mask) {
		case 0: return (row + col) % 2 === 0;
		case 1: return row % 2 === 0;
		case 2: return col % 3 === 0;
		case 3: return (row + col) % 3 === 0;
		case 4: return (Math.floor(row / 2) + Math.floor(col / 3)) % 2 === 0;
		case 5: return ((row * col) % 2 + (row * col) % 3) === 0;
		case 6: return (((row * col) % 2 + (row * col) % 3) % 2) === 0;
		case 7: return (((row + col) % 2 + (row * col) % 3) % 2) === 0;
		default: return false;
	}
};

const formatBits = (mask) => {
	const data = mask; // Error correction M uses format-level bits 00.
	let remainder = data << 10;
	const divisor = 0x537;
	for (let i = 14; i >= 10; i -= 1) {
		if ((remainder >>> i) & 1) remainder ^= divisor << (i - 10);
	}
	return (((data << 10) | remainder) ^ 0x5412) & 0x7fff;
};

const drawFormat = (matrix, mask) => {
	const bits = formatBits(mask);
	const bit = (index) => ((bits >>> index) & 1) !== 0;
	for (let i = 0; i <= 5; i += 1) matrix[i][8] = bit(i);
	matrix[7][8] = bit(6);
	matrix[8][8] = bit(7);
	matrix[8][7] = bit(8);
	for (let i = 9; i < 15; i += 1) matrix[8][14 - i] = bit(i);
	for (let i = 0; i < 8; i += 1) matrix[8][SIZE - 1 - i] = bit(i);
	for (let i = 8; i < 15; i += 1) matrix[SIZE - 15 + i][8] = bit(i);
	matrix[SIZE - 8][8] = true;
};

const placeData = (base, codewords, mask) => {
	const matrix = base.map((row) => row.slice());
	const bits = [];
	for (const byte of codewords) appendBits(bits, byte, 8);
	let bitIndex = 0;
	let upward = true;
	for (let right = SIZE - 1; right >= 1; right -= 2) {
		if (right === 6) right -= 1;
		for (let vertical = 0; vertical < SIZE; vertical += 1) {
			const row = upward ? SIZE - 1 - vertical : vertical;
			for (let offset = 0; offset < 2; offset += 1) {
				const col = right - offset;
				if (matrix[row][col] !== null) continue;
				let dark = bitIndex < bits.length ? bits[bitIndex] : false;
				if (maskBit(mask, row, col)) dark = !dark;
				matrix[row][col] = dark;
				bitIndex += 1;
			}
		}
		upward = !upward;
	}
	drawFormat(matrix, mask);
	return matrix;
};

const penalty = (matrix) => {
	let score = 0;
	for (const row of matrix) {
		let runColor = row[0];
		let run = 1;
		for (let i = 1; i < SIZE; i += 1) {
			if (row[i] === runColor) run += 1;
			else {
				if (run >= 5) score += 3 + run - 5;
				runColor = row[i];
				run = 1;
			}
		}
		if (run >= 5) score += 3 + run - 5;
	}
	for (let col = 0; col < SIZE; col += 1) {
		let runColor = matrix[0][col];
		let run = 1;
		for (let row = 1; row < SIZE; row += 1) {
			if (matrix[row][col] === runColor) run += 1;
			else {
				if (run >= 5) score += 3 + run - 5;
				runColor = matrix[row][col];
				run = 1;
			}
		}
		if (run >= 5) score += 3 + run - 5;
	}
	for (let row = 0; row < SIZE - 1; row += 1) {
		for (let col = 0; col < SIZE - 1; col += 1) {
			const value = matrix[row][col];
			if (matrix[row][col + 1] === value && matrix[row + 1][col] === value && matrix[row + 1][col + 1] === value) score += 3;
		}
	}
	const pattern = [true, false, true, true, true, false, true];
	for (let row = 0; row < SIZE; row += 1) {
		for (let col = 0; col <= SIZE - 7; col += 1) {
			let matches = true;
			for (let k = 0; k < 7; k += 1) if (matrix[row][col + k] !== pattern[k]) { matches = false; break; }
			if (!matches) continue;
			const before = col >= 4 && [1, 2, 3, 4].every((offset) => !matrix[row][col - offset]);
			const after = col + 10 < SIZE && [7, 8, 9, 10].every((offset) => !matrix[row][col + offset]);
			if (before || after) score += 40;
		}
	}
	for (let col = 0; col < SIZE; col += 1) {
		for (let row = 0; row <= SIZE - 7; row += 1) {
			let matches = true;
			for (let k = 0; k < 7; k += 1) if (matrix[row + k][col] !== pattern[k]) { matches = false; break; }
			if (!matches) continue;
			const before = row >= 4 && [1, 2, 3, 4].every((offset) => !matrix[row - offset][col]);
			const after = row + 10 < SIZE && [7, 8, 9, 10].every((offset) => !matrix[row + offset][col]);
			if (before || after) score += 40;
		}
	}
	let dark = 0;
	for (const row of matrix) for (const value of row) if (value) dark += 1;
	score += Math.floor(Math.abs(dark * 20 - SIZE * SIZE * 10) / (SIZE * SIZE)) * 10;
	return score;
};

export const verificationQrPayload = (safetyNumber) => {
	const digits = String(safetyNumber || '').replace(/\s+/g, '');
	if (!/^\d{40}$/.test(digits)) throw new Error('verification_qr_invalid_safety_number');
	return `${PREFIX}${digits}`;
};

export const matchesVerificationQrPayload = (raw, safetyNumber) => {
	try {
		return String(raw || '').trim() === verificationQrPayload(safetyNumber);
	} catch (_) {
		return false;
	}
};

export const createVerificationQrMatrix = (safetyNumber) => {
	const payload = verificationQrPayload(safetyNumber);
	const codewords = interleave(encodeData(payload));
	const base = buildBase();
	let best = null;
	let bestScore = Infinity;
	for (let mask = 0; mask < 8; mask += 1) {
		const matrix = placeData(base, codewords, mask);
		const score = penalty(matrix);
		if (score < bestScore) {
			best = matrix;
			bestScore = score;
		}
	}
	return best;
};

export const createVerificationQrSvg = (safetyNumber, { scale = 6, margin = 4 } = {}) => {
	const matrix = createVerificationQrMatrix(safetyNumber);
	const dimension = (SIZE + margin * 2) * scale;
	let path = '';
	for (let row = 0; row < SIZE; row += 1) {
		for (let col = 0; col < SIZE; col += 1) {
			if (matrix[row][col]) path += `M${(col + margin) * scale} ${(row + margin) * scale}h${scale}v${scale}h-${scale}z`;
		}
	}
	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${dimension} ${dimension}" width="${dimension}" height="${dimension}" role="img" aria-label="QR-код проверки E2EE"><rect width="100%" height="100%" fill="#fff"/><path d="${path}" fill="#000"/></svg>`;
};
