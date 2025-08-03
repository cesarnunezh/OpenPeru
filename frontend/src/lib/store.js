export const API_URL = 'http://127.0.0.1:8000/v1';

export function getData(endpoint) {
	return fetch(`${API_URL}${endpoint}`)
		.then((response) => {
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			return response.json();
		})
		.catch((error) => {
			console.error('Error fetching data:', error);
			throw error;
		});
}
