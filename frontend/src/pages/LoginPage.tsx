import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowRight, Lock, Mail, User as UserIcon } from 'lucide-react';

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
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);

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
        <div className="mx-auto w-full max-w-md">
          <Brand className="mb-10" />

          <h1 className="font-display text-3xl font-bold tracking-tight">Sign in</h1>
          <p className="mt-2 text-muted-foreground">
            Welcome back. Access your farm dashboards, predictions and saved reports.
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

            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              icon={<Lock className="h-4 w-4" aria-hidden="true" />}
              error={errors.password?.message}
              {...register('password')}
            />

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

      <div className="relative hidden overflow-hidden bg-brand-950 lg:block">
        <div className="absolute inset-0 bg-grid-dark bg-grid-dark opacity-40" />
        <div className="relative flex h-full flex-col justify-center px-16 text-white">
          <UserIcon className="mb-6 h-10 w-10 text-brand-400" aria-hidden="true" />
          <p className="font-display text-3xl font-bold leading-tight">
            Every prediction is backed by a model that was actually trained and measured.
          </p>
          <p className="mt-4 max-w-md text-sm text-white/70">
            AgriVision AI refuses to return a result it cannot back with real metrics.
            When a model is not installed, the API says so instead of guessing.
          </p>
        </div>
      </div>
    </div>
  );
}
