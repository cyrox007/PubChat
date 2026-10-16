import $api from '.';

export default class CallService {
	static iceConfig() {
		return $api.get('/calls/v1/ice-config');
	}
}
