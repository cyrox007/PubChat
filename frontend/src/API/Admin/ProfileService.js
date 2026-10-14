import $api from "@/API/index";

export default class ProfileService {
	static async getUsers(params = {}) {
		const response = await $api.get('/admin/users', { params });
		return {
			data: response.data.users || [],
			total: response.data.meta?.total || 0,
			meta: response.data.meta || {}
		};
	}

	static async getUserOverview(uid) {
		return await $api.get(`/admin/users/${uid}/overview`);
	}

	static async getUserRooms(uid) {
		return await $api.get(`/admin/users/${uid}/rooms`);
	}

	static async getUserPenalties(uid) {
		return await $api.get(`/admin/users/${uid}/penalties`);
	}

	static async assignPenalty(data) {
		return await $api.post('/admin/penalties/assign', data);
	}

	static async deletePenalty(id) {
		return await $api.delete(`/admin/penalties/${id}`);
	}

	static async updateAdminProfile(uid, data) {
		return await $api.put(`/admin/users/${uid}`, { data });
	}
}
