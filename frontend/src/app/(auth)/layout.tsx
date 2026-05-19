export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-gradient-to-br from-background via-background to-primary-subtle p-4">
      {children}
    </div>
  );
}
