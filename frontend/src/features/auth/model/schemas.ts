import { z } from 'zod';

export const authCredentialsSchema = z.object({
  email: z.string().trim().email('Некорректный формат электронной почты'),
  password: z.string().min(8, 'Пароль должен содержать минимум 8 символов'),
});

export type AuthCredentialsInput = z.infer<typeof authCredentialsSchema>;
