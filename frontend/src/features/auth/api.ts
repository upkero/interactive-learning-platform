import { apiClient } from '@/shared/api/client';
import type { paths } from '@/shared/api/schema';

export type LoginCredentials =
  paths['/api/v1/auth/login']['post']['requestBody']['content']['application/json'];

export type RegisterCredentials =
  paths['/api/v1/auth/register']['post']['requestBody']['content']['application/json'];

export async function login(credentials: LoginCredentials) {
  const { data } = await apiClient.POST('/api/v1/auth/login', { body: credentials });
  return data;
}

export async function register(credentials: RegisterCredentials) {
  const { data } = await apiClient.POST('/api/v1/auth/register', { body: credentials });
  return data;
}

export async function logout() {
  await apiClient.POST('/api/v1/auth/logout');
}
