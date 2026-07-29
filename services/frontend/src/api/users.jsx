import apiClient from '../utils/apiClient';
import { USER_SERVICE_URL } from '../config/serviceUrls';
import { parseApiError } from './errors';

// F2-08: user-services første skrive-sti til en eksisterende bruger.
//
// IKKE createCrudApi. Profilen er ikke en CRUD-ressource — der er ingen
// liste, intet id i URL'en og ingen delete; ruterne er felt-specifikke
// (/me/password, /me/username) netop fordi et password-skift kræver
// current_password og et navneskift ikke gør.
//
// PUT og ikke PATCH: apiClient har ingen patch-metode (utils/apiClient.jsx),
// og ruterne udskifter hele det felt de navngiver.

async function putOrThrow(path, body) {
  const response = await apiClient.put(`${USER_SERVICE_URL}${path}`, body);
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response;
}

export async function fetchMe() {
  const response = await apiClient.get(`${USER_SERVICE_URL}/me`);
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.json();
}

/**
 * Skift adgangskode. Svarer 204 uden krop.
 *
 * Bemærk 403 ved forkert `current_password` — bevidst ikke 401.
 * apiClient's 401-gren kalder handleUnauthorized() og redirecter til
 * /login, så en 401 herfra ville logge brugeren ud på en tastefejl.
 * Fejlen når derfor frem som en ApiError kalderen kan vise.
 */
export async function changePassword({ current_password, new_password }) {
  await putOrThrow('/me/password', { current_password, new_password });
}

/** Skift brugernavn. Returnerer den opdaterede bruger. */
export async function changeUsername({ username }) {
  const response = await putOrThrow('/me/username', { username });
  return response.json();
}
