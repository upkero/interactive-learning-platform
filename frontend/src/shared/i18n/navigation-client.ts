"use client";

import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";
import { useSearchParams as useNextSearchParams } from "next/navigation";

export const { usePathname, useRouter } = createNavigation(routing);
export const useSearchParams = useNextSearchParams;
export {
  usePathname as useNextPathname,
  useRouter as useNextRouter,
} from "next/navigation";
