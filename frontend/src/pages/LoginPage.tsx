import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowRight, Eye, EyeOff, Lock, Mail, Leaf, Sprout } from 'lucide-react';

import { Brand } from '@/components/layout/Brand';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Form';
import { Alert } from '@/components/ui/Alert';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/contexts/ToastContext';
import { ApiError } from '@/services/api';

const schema = z.object({
  email: z.string().min(1, 'Enter your email address.').email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
});

type LoginForm = z.infer<typeof schema>;

export function LoginPage() {
  const { login } = useAuth();
  const toast = useToast();
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const redirectTo = (location.state as { from?: string } | null)?.from ?? '/dashboard';

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const user = await login(values);
      toast.success(`Welcome back, ${user.name.split(' ')[0]}!`);
      navigate(user.role === 'admin' && redirectTo === '/dashboard' ? '/dashboard' : redirectTo, {
        replace: true,
      });
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Unable to sign in right now. Please try again.';
      setServerError(message);
    }
  });

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-20">
        <div className="flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-20">
          <div className="mx-auto w-full max-w-md">
            <Link to="/">
              <Brand className="mb-10" />
            </Link>

            <h1 className="font-display text-3xl font-bold tracking-tight">Sign in to Agri-AI</h1>
            <p className="mt-2 text-muted-foreground">
              Welcome back. Access your farm dashboard and AI-powered insights.
            </p>

          {serverError ? (
            <Alert tone="danger" className="mt-6" title="Sign-in failed">
              {serverError}
            </Alert>
          ) : null}

            <form onSubmit={onSubmit} className="mt-8 space-y-5" noValidate>
              <Input
                label="Email address"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                icon={<Mail className="h-4 w-4" aria-hidden="true" />}
                error={errors.email?.message}
                {...register('email')}
              />

              <div className="space-y-1.5">
                <label htmlFor="password" className="text-sm font-medium text-foreground">
                  Password
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    <Lock className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 pl-9 pr-10 text-sm text-foreground shadow-sm transition placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60"
                    {...register('password')}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password?.message ? (
                  <p className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                    {errors.password?.message}
                  </p>
                ) : null}
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded border-input text-brand-600 focus:ring-ring"
                  />
                  <span className="text-sm text-muted-foreground">Remember me</span>
                </label>
                <Link
                  to="/forgot-password"
                  className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-400"
                >
                  Forgot Password?
                </Link>
              </div>

              <Button type="submit" size="lg" fullWidth isLoading={isSubmitting}>
                Sign in
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Do not have an account?{' '}
            <Link
              to="/register"
              className="focus-ring rounded font-medium text-brand-700 hover:underline dark:text-brand-400"
            >
              Create one
            </Link>
          </p>
        </div>
      </div>

      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-950 via-emerald-900 to-green-950 lg:block">
        <div className="absolute inset-0">
          <img
            src="/images/agriculture/hero-farm.jpg"
            alt="Agricultural farm field"
            className="h-full w-full object-cover opacity-40"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-brand-950/90 to-brand-950/60" />
        </div>
        <div className="relative flex h-full flex-col justify-center px-16 text-white">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-2 backdrop-blur">
            <Leaf className="h-5 w-5 text-brand-400" aria-hidden="true" />
            <span className="text-sm font-medium">Smart Farming, Better Future</span>
          </div>
          <h2 className="font-display text-4xl font-bold leading-tight">
            Transform Your Farming with AI
          </h2>
          <p className="mt-4 max-w-md text-lg text-white/80">
            Detect crop diseases instantly, get smart recommendations, and make data-driven decisions for better yields.
          </p>
          <div className="mt-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500/20">
                <Leaf className="h-5 w-5 text-brand-400" />
              </div>
              <div>
                <p className="font-medium">AI Disease Detection</p>
                <p className="text-sm text-white/70">98% accurate disease identification</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500/20">
                <Sprout className="h-5 w-5 text-brand-400" />
              </div>
              <div>
                <p className="font-medium">Smart Crop Recommendations</p>
                <p className="text-sm text-white/70">Personalized suggestions for your farm</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
