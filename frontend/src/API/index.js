import axios from "axios";
import store from "@/stores";
import { clearAccessToken, getAccessToken, setAccessToken } from "@/API/session";
import { AUTH_DEVICE_HEADER, getAuthDeviceId } from '@/API/authDevice';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const UNSAFE_METHODS = new Set(['post', 'put', 'patch', 'delete']);

// A full document navigation cancels in-flight XHR in WebKit. Give safe reads
// an explicit cancellation lifecycle before the browser tears down the page,
// instead of leaving their promises to fail with an access-control error.
// Never cancel mutations or realtime ticket issuance here: the server may
// already have committed the operation.
const READ_ONLY_POST_PATHS = new Set([
    '/identity/v2/personas/batch',
    '/users/statuses',
    '/spaces/v1/live-state',
]);
const pendingDocumentReads = new Set();
const shouldCancelOnPageHide = (requestConfig) => {
    const method = String(requestConfig.method || 'get').toLowerCase();
    const path = String(requestConfig.url || '').split('?')[0];
    return method === 'get' || (method === 'post' && READ_ONLY_POST_PATHS.has(path));
};

const releaseDocumentRead = (requestConfig) => {
    const controller = requestConfig?._documentReadController;
    if (controller) pendingDocumentReads.delete(controller);
};

if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', () => {
        for (const controller of pendingDocumentReads) controller.abort('document navigation');
        pendingDocumentReads.clear();
    });
}

const $api = axios.create({
    withCredentials: true,
    baseURL: API_BASE_URL,
});

let csrfToken = null;
let csrfPromise = null;
let isRefreshing = false;
let failedQueue = [];

const normalizeAvatarUrl = (value) => {
    if (!value || typeof value !== 'string') return value;
    if (/^(https?:|blob:|data:)/i.test(value)) return value;
    const path = value.startsWith('/') ? value : `/${value}`;
    return `${window.location.origin}${path}`;
};

const normalizePublicAssetFields = (value) => {
    if (Array.isArray(value)) return value.map((item) => normalizePublicAssetFields(item));
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(
        Object.entries(value).map(([key, child]) => [
            key,
            key === 'avatar' ? normalizeAvatarUrl(child) : normalizePublicAssetFields(child),
        ]),
    );
};

export const clearCsrfToken = () => {
    csrfToken = null;
};

export const ensureCsrfToken = async (force = false) => {
    if (!force && csrfToken) return csrfToken;
    if (!force && csrfPromise) return csrfPromise;

    csrfPromise = axios.get(`${API_BASE_URL}/csrf/get`, {
        withCredentials: true,
        headers: { 'Cache-Control': 'no-cache', [AUTH_DEVICE_HEADER]: getAuthDeviceId() },
    }).then((response) => {
        const token = response.data?.csrf_token;
        if (!token || typeof token !== 'string') {
            throw new Error('CSRF bootstrap response did not include a token');
        }
        csrfToken = token;
        return token;
    }).finally(() => {
        csrfPromise = null;
    });

    return csrfPromise;
};

const clearSessionStorage = () => {
    clearAccessToken();
    clearCsrfToken();
    localStorage.removeItem('auth');
    localStorage.removeItem('user');
    localStorage.removeItem('identity');
    localStorage.removeItem('access_token');
};

const expireSession = () => {
    clearSessionStorage();
    store.dispatch('clearUser');
    window.dispatchEvent(new CustomEvent('pubchat:session-expired'));
};

const processQueue = (error = null, accessToken = null) => {
    failedQueue.forEach(({ resolve, reject, request }) => {
        if (error) {
            reject(error);
            return;
        }
        request.headers.Authorization = `Bearer ${accessToken}`;
        resolve($api(request));
    });
    failedQueue = [];
};

$api.interceptors.request.use(async (requestConfig) => {
    const config = requestConfig;
    const method = String(config.method || 'get').toLowerCase();
    config.headers = config.headers || {};
    config.headers[AUTH_DEVICE_HEADER] = getAuthDeviceId();
    if (shouldCancelOnPageHide(config)) {
        // WebKit may report navigation-interrupted XMLHttpRequest as an
        // access-control failure even though the destination is same-origin.
        // Fetch has predictable cancellation semantics for read-only traffic.
        // Keep Axios/XHR for mutations and uploads so their semantics do not change.
        config.adapter = 'fetch';
        if (!config.signal) {
            const controller = new AbortController();
            config.signal = controller.signal;
            config._documentReadController = controller;
            pendingDocumentReads.add(controller);
        }
    }

    if (UNSAFE_METHODS.has(method)) {
        const token = await ensureCsrfToken();
        config.headers[CSRF_HEADER_NAME] = token;
    }

    const accessToken = getAccessToken();
    if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
});

$api.interceptors.response.use(
    (response) => {
        releaseDocumentRead(response.config);
        response.data = normalizePublicAssetFields(response.data);
        return response;
    },
    async (error) => {
        releaseDocumentRead(error.config);
        const originalRequest = error.config;
        const status = error.response?.status;
        const detail = error.response?.data?.detail;
        const isIdentityRefresh = originalRequest?.url?.includes('/identity/v2/refresh');
        const isCsrfFailure = status === 403 && typeof detail === 'string' && detail.includes('CSRF');
        const isAccountAccessRestriction = (
            status === 403
            && detail
            && typeof detail === 'object'
            && detail.error_type === 'account_access_restricted'
        );

        if (isAccountAccessRestriction) {
            store.commit('setAccessRestriction', detail.restriction || null);
            window.dispatchEvent(new CustomEvent('pubchat:account-access-restricted'));
            return Promise.reject(error);
        }

        if (isCsrfFailure && !originalRequest?._csrfRetry) {
            originalRequest._csrfRetry = true;
            try {
                const token = await ensureCsrfToken(true);
                originalRequest.headers = originalRequest.headers || {};
                originalRequest.headers[CSRF_HEADER_NAME] = token;
                return $api(originalRequest);
            } catch (csrfError) {
                return Promise.reject(csrfError);
            }
        }

        if (status === 401 && !originalRequest?._isRetry && !isIdentityRefresh) {
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject, request: originalRequest });
                });
            }

            isRefreshing = true;
            originalRequest._isRetry = true;

            try {
                const csrf = await ensureCsrfToken(true);
                const refreshResponse = await axios.post(
                    `${API_BASE_URL}/identity/v2/refresh`,
                    {},
                    {
                        withCredentials: true,
                        headers: {
                            [CSRF_HEADER_NAME]: csrf,
                            [AUTH_DEVICE_HEADER]: getAuthDeviceId(),
                        },
                    }
                );
                const accessToken = refreshResponse.data.access_token;
                setAccessToken(accessToken);
                if (refreshResponse.data.access_restriction) {
                    store.commit('setAccessRestriction', refreshResponse.data.access_restriction);
                    window.dispatchEvent(new CustomEvent('pubchat:account-access-restricted'));
                }
                originalRequest.headers = originalRequest.headers || {};
                originalRequest.headers.Authorization = `Bearer ${accessToken}`;
                processQueue(null, accessToken);
                return $api(originalRequest);
            } catch (refreshError) {
                processQueue(refreshError);
                expireSession();
                return Promise.reject(refreshError);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);

export default $api;
