"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MapPin, Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { login, createSession } from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

export default function LoginPage() {
  const router = useRouter();
  const { setUser, setSession } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const loginRes = await login(email, password);
      setUser(loginRes.access_token, email);

      const sessionRes = await createSession(loginRes.access_token);
      setSession(sessionRes.session_id, sessionRes.token.access_token);

      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("登录失败，请稍后重试");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-[400px] border-border-subtle shadow-lg">
      <CardHeader className="items-center space-y-2 pb-2">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <MapPin className="h-6 w-6" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">如途</h1>
        <p className="text-sm text-muted-foreground">AI 旅行规划助手</p>
      </CardHeader>

      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {error && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="email">邮箱</Label>
            <Input
              id="email"
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <Button type="submit" className="w-full" size="lg" disabled={loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            登录
          </Button>
        </CardContent>
      </form>

      <CardFooter className="justify-center">
        <p className="text-sm text-muted-foreground">
          没有账号？{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            立即注册
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
