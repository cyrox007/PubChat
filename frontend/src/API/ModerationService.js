import $api from '.';

export default class ModerationService {
	static myReports(params = {}) {
		return $api.get('/moderation/v1/me/reports', { params });
	}

	static myActions(params = {}) {
		return $api.get('/moderation/v1/me/actions', { params });
	}

	static myAppeals(params = {}) {
		return $api.get('/moderation/v1/me/appeals', { params });
	}

	static appeal(actionUid, body) {
		return $api.post(`/moderation/v1/actions/${actionUid}/appeals`, { body });
	}

	static createReport(spaceUid, payload) {
		return $api.post(`/moderation/v1/spaces/${spaceUid}/reports`, payload);
	}

	static reports(spaceUid, params = {}) {
		return $api.get(`/moderation/v1/spaces/${spaceUid}/reports`, { params });
	}

	static updateReport(spaceUid, reportUid, status) {
		return $api.patch(`/moderation/v1/spaces/${spaceUid}/reports/${reportUid}`, { status });
	}

	static createAction(spaceUid, payload) {
		return $api.post(`/moderation/v1/spaces/${spaceUid}/actions`, payload);
	}

	static actions(spaceUid, params = {}) {
		return $api.get(`/moderation/v1/spaces/${spaceUid}/actions`, { params });
	}

	static appeals(spaceUid, params = {}) {
		return $api.get(`/moderation/v1/spaces/${spaceUid}/appeals`, { params });
	}

	static resolveAppeal(spaceUid, appealUid, payload) {
		return $api.patch(`/moderation/v1/spaces/${spaceUid}/appeals/${appealUid}`, payload);
	}

	static createTrustSafetyReport(payload) {
		return $api.post('/trust-safety/v1/reports', payload);
	}

	static myTrustSafetyReports(params = {}) {
		return $api.get('/trust-safety/v1/me/reports', { params });
	}

	static trustSafetyQueue(params = {}) {
		return $api.get('/trust-safety/v1/queue', { params });
	}

	static abuseSignals(params = {}) {
		return $api.get('/trust-safety/v1/abuse-signals', { params });
	}

	static trustSafetyMetrics(params = {}) {
		return $api.get('/trust-safety/v1/metrics', { params });
	}

	static reviewAbuseSignal(signalUid, payload) {
		return $api.patch(`/trust-safety/v1/abuse-signals/${signalUid}`, payload);
	}

	static claimTrustSafetyReport(reportUid) {
		return $api.post(`/trust-safety/v1/reports/${reportUid}/claim`);
	}

	static releaseTrustSafetyReport(reportUid) {
		return $api.post(`/trust-safety/v1/reports/${reportUid}/release`);
	}

	static trustSafetyEvidence(reportUid) {
		return $api.get(`/trust-safety/v1/reports/${reportUid}/evidence`);
	}

	static decideTrustSafetyReport(reportUid, payload) {
		return $api.patch(`/trust-safety/v1/reports/${reportUid}`, payload);
	}

	static trustSafetyAudit(reportUid, params = {}) {
		return $api.get(`/trust-safety/v1/reports/${reportUid}/audit`, { params });
	}

	static moderationMediaRecords(reportUid) {
		return $api.get(`/trust-safety/v1/reports/${reportUid}/media-records`);
	}

	static quarantineModerationMedia(reportUid, attachmentIndex, payload) {
		return $api.post(`/trust-safety/v1/reports/${reportUid}/media/${attachmentIndex}/quarantine`, payload);
	}

	static restoreModerationMedia(reportUid, recordUid) {
		return $api.post(`/trust-safety/v1/reports/${reportUid}/media-records/${recordUid}/restore`);
	}

	static removeModerationMedia(reportUid, recordUid, payload) {
		return $api.post(`/trust-safety/v1/reports/${reportUid}/media-records/${recordUid}/remove`, payload);
	}

	static lexiconPolicy() {
		return $api.get('/trust-safety/v1/lexicon');
	}

	static lexiconRevision(revision) {
		return $api.get(`/trust-safety/v1/lexicon/revisions/${revision}`);
	}

	static saveLexiconRevision(body) {
		return $api.post('/trust-safety/v1/lexicon/revisions', body);
	}

	static activateLexiconRevision(body) {
		return $api.post('/trust-safety/v1/lexicon/activate', body);
	}

	static simulateLexicon(body) {
		return $api.post('/trust-safety/v1/lexicon/simulate', body);
	}

	static lexiconAudit(params = {}) {
		return $api.get('/trust-safety/v1/lexicon/audit', { params });
	}

	static moderationAIConfig() {
		return $api.get('/trust-safety/v1/ai-assessment/config');
	}

	static moderationAIAssessments(reportUid, params = {}) {
		return $api.get(`/trust-safety/v1/reports/${reportUid}/ai-assessments`, { params });
	}

	static createModerationAIAssessment(reportUid) {
		return $api.post(`/trust-safety/v1/reports/${reportUid}/ai-assessments`);
	}

	static setModerationAIOutcome(reportUid, assessmentUid, payload) {
		return $api.patch(`/trust-safety/v1/reports/${reportUid}/ai-assessments/${assessmentUid}`, payload);
	}

	static restrictionCapabilities() {
		return $api.get('/trust-safety/v1/restriction-capabilities');
	}

	static createRestriction(payload) {
		return $api.post('/trust-safety/v1/restrictions', payload);
	}

	static targetRestrictions(targetAccountUid, params = {}) {
		return $api.get('/trust-safety/v1/restrictions', {
			params: { target_account_uid: targetAccountUid, ...params },
		});
	}

	static myRestrictions(params = {}) {
		return $api.get('/trust-safety/v1/me/restrictions', { params });
	}

	static revokeRestriction(restrictionUid, reason) {
		return $api.post(`/trust-safety/v1/restrictions/${restrictionUid}/revoke`, { reason });
	}

	static appealRestriction(restrictionUid, body) {
		return $api.post(`/trust-safety/v1/restrictions/${restrictionUid}/appeals`, { body });
	}

	static myRestrictionAppeals(params = {}) {
		return $api.get('/trust-safety/v1/me/restriction-appeals', { params });
	}

	static restrictionAppeals(params = {}) {
		return $api.get('/trust-safety/v1/restriction-appeals', { params });
	}

	static claimRestrictionAppeal(appealUid) {
		return $api.post(`/trust-safety/v1/restriction-appeals/${appealUid}/claim`);
	}

	static releaseRestrictionAppeal(appealUid) {
		return $api.post(`/trust-safety/v1/restriction-appeals/${appealUid}/release`);
	}

	static resolveRestrictionAppeal(appealUid, payload) {
		return $api.patch(`/trust-safety/v1/restriction-appeals/${appealUid}`, payload);
	}
}
