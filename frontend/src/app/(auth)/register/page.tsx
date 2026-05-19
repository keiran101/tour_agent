"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MapPin, Eye, EyeOff, Loader2, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { register, createSession } from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

const PASSWORD_RULES = [
  { label: "至少 8 个字符", test: (p: string) => p.length >= 8 },
  { label: "包含大写字母", test: (p: string) => /[A-Z]/.test(p) },
  { label: "包含小写字母", test: (p: string) => /[a-z]/.test(p) },
  { label: "包含数字", test: (p: string) => /\d/.test(p) },
  { label: "包含特殊字符", test: (p: string) => /[^A-Za-z0-9]/.test(p) },
];

export default function RegisterPage() {
  const router = useRouter();
  const { setUser, setSession } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const allRulesPass = PASSWORD_RULES.every((r) => r.test(password));
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!allRulesPass) {
      setError("密码不符合要求");
      return;
    }
    if (!passwordsMatch) {
      setError("两次密码输入不一致");
      return;
    }

    setLoading(true);
    try {
      const res = await register({ email, password });
      setUser(res.token.access_token, email);

      const sessionRes = await createSession(res.token.access_token);
      setSession(sessionRes.session_id, sessionRes.token.access_token);

      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("注册失败，请稍后重试");
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
        <h1 className="text-2xl font-bold tracking-tight">创建账号</h1>
        <p className="text-sm text-muted-foreground">开始你的智能旅行规划</p>
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
                placeholder="设置密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
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
            {password.length > 0 && (
              <ul className="space-y-1 pt-1">
                {PASSWORD_RULES.map((rule) => {
                  const pass = rule.test(password);
                  return (
                    <li
                      key={rule.label}
                      className={`flex items-center gap-1.5 text-xs ${pass ? "text-success" : "text-muted-foreground"}`}
                    >
                      {pass ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                      {rule.label}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm-password">确认密码</Label>
            <Input
              id="confirm-password"
              type={showPassword ? "text" : "password"}
              placeholder="再次输入密码"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>

          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={loading || !allRulesPass || !passwordsMatch}
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            注册
          </Button>
        </CardContent>
      </form>

      <CardFooter className="justify-center">
        <p className="text-sm text-muted-foreground">
          已有账号？{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            登录
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
