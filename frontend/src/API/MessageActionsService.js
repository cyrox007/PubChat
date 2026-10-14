import $api from '@/API';

export default class MessageActionsService {
  static edit(surface, uid, content) {
    return $api.patch(`/messages/v2/${surface}/${uid}`, { content });
  }

  static remove(surface, uid) {
    return $api.delete(`/messages/v2/${surface}/${uid}`);
  }

  static reply(surface, uid, content) {
    return $api.post(`/messages/v2/${surface}/${uid}/reply`, { content });
  }

  static reactions(surface, uid) {
    return $api.get(`/messages/v2/${surface}/${uid}/reactions`);
  }

  static react(surface, uid, emoji) {
    return $api.post(`/messages/v2/${surface}/${uid}/reactions`, { emoji });
  }

  static forward(surface, uid, targetSurface, targetUid) {
    return $api.post(`/messages/v2/${surface}/${uid}/forward`, {
      target_surface: targetSurface,
      target_uid: targetUid,
    });
  }
}
