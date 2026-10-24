"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import Logo from "@/components/Logo";
import { Button, ErrorText, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isSignup = mode === "signup";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { access_token } = isSignup ? await api.signup(email, password) : await api.login(email, password);
      setToken(access_token);
      router.push("/dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5 rounded-2xl border border-line p-6">
        <div>
          <Logo />
          <h1 className="mt-4 text-2xl font-semibold">{isSignup ? "Create your account" : "Welcome back"}</h1>
        </div>
        <Field label="Email">
          <Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password" hint={isSignup ? "At least 8 characters" : undefined}>
          <Input
            type="password"
            autoComplete={isSignup ? "new-password" : "current-password"}
            required
            minLength={isSignup ? 8 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button className="w-full" disabled={busy}>
          {busy ? "Please wait…" : isSignup ? "Create account" : "Log in"}
        </Button>
        <p className="text-center text-sm text-ink-2">
          {isSignup ? "Already have an account? " : "New here? "}
          <Link href={isSignup ? "/login" : "/signup"} className="text-accent hover:underline">
            {isSignup ? "Log in" : "Create an account"}
          </Link>
        </p>
      </form>
    </main>
  );
}
