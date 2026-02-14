
import axios from 'axios';



// Create an Axios instance
const getBaseUrl = () => {
  // If running on localhost (computer), use localhost
  if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
    return 'http://localhost:8000';
  }
  // If running on network (mobile), use the same hostname (computer IP) + port 8000
  if (typeof window !== 'undefined') {
    return `http://${window.location.hostname}:8000`;
  }
  return 'http://localhost:8000'; // Fallback
};

const api = axios.create({
  baseURL: getBaseUrl(), // Backend URL
  timeout: 30000, // 30 seconds timeout (increased for complex operations)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor
api.interceptors.request.use(
  (config) => {
    // Get the token from local storage
    const token = localStorage.getItem('studySpace_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },

  (error) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor to handle 401s (Token Expiry)
// DO NOT redirect here - just clear the tokens and let React handle the auth state
// Redirecting from interceptor causes infinite loops when page reloads

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      console.warn("Session expired or invalid token. Clearing auth data...");
      localStorage.removeItem('studySpace_token');
      localStorage.removeItem('studySpace_user');
      // DO NOT redirect here - the React auth guard will show login page
      // when appState.currentUser becomes null on next rerender/refresh
    }
    return Promise.reject(error);
  }
);


export default api;
