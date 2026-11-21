import { z } from 'zod';

export const authCredentialsSchema = z.object({
  email: z.string().trim().email({ message: 'invalid_email' }),
  password: z.string().min(8, { message: 'password_too_short' }),
});

export type AuthCredentialsInput = z.infer<typeof authCredentialsSchema>;
