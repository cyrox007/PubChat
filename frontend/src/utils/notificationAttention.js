/**
 * Present only newly received foreground events. When a person already sees the
 * exact conversation, its new message is the feedback: never duplicate an alert.
 * Hidden/background pages use the operating system Push channel instead.
 */
export const isViewingNotificationTarget = (notice, routeName, roomUid, activeDialog) => (
    (notice?.surface === 'space'
        && String(routeName || '').startsWith('space')
        && String(roomUid || '') === String(notice.roomUid || ''))
    || (notice?.surface === 'messenger'
        && routeName === 'messenger'
        && activeDialog === notice.userId)
);

export const shouldShowForegroundNotice = (
    notice, { visibilityState, routeName, roomUid, activeDialog },
) => Boolean(
    notice?.uid
    && visibilityState === 'visible'
    && routeName !== 'notifications'
    && !isViewingNotificationTarget(notice, routeName, roomUid, activeDialog)
);
