import { GraphQLClient } from 'graphql-request';
import { handleUnauthorized } from '../utils/handleUnauthorized';

const GRAPHQL_URL =
  (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1') + '/graphql';

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('access_token');
  const accountId = localStorage.getItem('account_id');

  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (accountId) headers['X-Account-ID'] = accountId;

  return headers;
}

export function getGraphQLClient() {
  return new GraphQLClient(GRAPHQL_URL, { headers: getHeaders() });
}

export async function gqlRequest(query, variables = {}) {
  const client = getGraphQLClient();
  try {
    return await client.request(query, variables);
  } catch (error) {
    if (error.response?.status === 401) {
      handleUnauthorized();
      return new Promise(() => {});
    }
    throw error;
  }
}
