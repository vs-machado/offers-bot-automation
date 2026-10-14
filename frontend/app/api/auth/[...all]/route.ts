import { toNextJsHandler } from "better-auth/next-js";
import { getAuth } from "@/auth";

export function GET(request: Request) { return toNextJsHandler(getAuth()).GET(request); }
export function POST(request: Request) { return toNextJsHandler(getAuth()).POST(request); }
