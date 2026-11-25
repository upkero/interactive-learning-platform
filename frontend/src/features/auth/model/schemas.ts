import { z } from "zod";

export const authCredentialsSchema = z.object({
  email: z.string().trim().email({ message: "invalid_email" }),
  password: z.string().min(8, { message: "password_too_short" }),
});

export const registerSchema = authCredentialsSchema.extend({
  display_name: z
    .string()
    .trim()
    .max(100, { message: "display_name_too_long" })
    .optional(),
});

export type AuthCredentialsInput = z.infer<typeof authCredentialsSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
