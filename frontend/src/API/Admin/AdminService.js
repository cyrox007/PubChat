import $api from '@/API';

export default class AdminService {
	static async getDashboardStats() {
		return $api.get('/admin/dashboard/stats');
	}

	static async getOnlineUsers() {
		return $api.get('/admin/users/online');
	}

	static async getRoomStats() {
		return $api.get('/admin/rooms/stats');
	}

	static async getExternalDeliveryMetrics(windowHours = 24) {
		return $api.get('/admin/operations/external-delivery', { params: { window_hours: windowHours } });
	}

	static async getRealtimeRedisMetrics() {
		return $api.get('/admin/operations/realtime-redis');
	}

	static async getPostgresPoolMetrics() {
		return $api.get('/admin/operations/postgres-pool');
	}

	static async getHttpMetrics() {
		return $api.get('/admin/operations/http');
	}
}