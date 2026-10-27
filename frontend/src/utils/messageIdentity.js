/**
 * One optimistic row survives the transition frontId -> canonical database uid.
 * A uid is authoritative. A frontId is scoped to its original conversation
 * and author; two different accounts must never merge each other's rows.
 */
export const stableMessageKey = (message) => message?.frontId || message?.uid || message?.tempId || null;

export function sameMessage(left, right) {
  if (!left || !right) return false;
  if (left.uid && right.uid && left.uid === right.uid) return true;
  if (!left.frontId || !right.frontId || left.frontId !== right.frontId) return false;
  const from = (item) => item.sender_uid || item.sender?.uid || item.author_uid || null;
  const leftFrom = from(left), rightFrom = from(right);
  if (leftFrom && rightFrom && String(leftFrom) !== String(rightFrom)) return false;
  const scope = (item) => item.room_uid || item.receiver_uid || null;
  const leftScope = scope(left), rightScope = scope(right);
  return !leftScope || !rightScope || String(leftScope) === String(rightScope);
}

export function mergeMessage(oldValue, incoming) {
  const committed = Boolean(incoming.uid);
  return {
    ...oldValue,
    ...incoming,
    frontId: incoming.frontId || oldValue?.frontId || null,
    status: committed ? 'sent' : (incoming.status || oldValue?.status || 'sending'),
  };
}

export function upsertMessage(items, incoming) {
  const index = items.findIndex((item) => sameMessage(item, incoming));
  if (index === -1) return [...items, mergeMessage(null, incoming)];
  const copy = [...items];
  copy[index] = mergeMessage(items[index], incoming);
  return copy;
}
