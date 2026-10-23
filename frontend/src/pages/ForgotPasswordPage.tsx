import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowLeft, ArrowRight, Mail } from 'lucide-react';

import { Brand } from '@/components/layout/Brand';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Form';
import { Alert } from '@/components/ui/Alert';
import { authService } from '@/services/auth';
import { ApiError } from '@/services/api';

const schema = z.object({
  email: z.string().min(1, 'Enter your email address.').email('Enter a valid email address.'),
});

type ForgotForm = z.infer<typeof schema>;

export function ForgotPasswordPage() {
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotForm>({
    resolver: zodResolver(schema),
    defaultValues: { email: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await authService.forgotPassword(values.email);
      setSuccess(true);
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Unable to send reset email. Please try again.';
      setServerError(message);
    }
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 via-white to-emerald-50 dark:from-gray-950 dark:via-gray-900 dark:to-brand-950">
      <div className="container mx-auto px-4 py-8">
        <Link to="/">
          <Brand />
        </Link>
      </div>

      <div className="container mx-auto flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-border bg-card p-8 shadow-xl">
            {!success ? (
              <>
                <h1 className="font-display text-2xl font-bold tracking-tight">Forgot Your Password?</h1>
                <p className="mt-2 text-muted-foreground">
                  Enter your registered email address and we'll send you a link to reset your password.
                </p>

                {serverError ? (
                  <Alert tone="danger" className="mt-6" title="Error">
                    {serverError}
                  </Alert>
                ) : null}

                <form onSubmit={onSubmit} className="mt-6 space-y-5" noValidate>
                  <Input
                    label="Email address"
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    icon={<Mail className="h-4 w-4" aria-hidden="true" />}
                    error={errors.email?.message}
                    {...register('email')}
                  />

                  <Button type="submit" size="lg" fullWidth isLoading={isSubmitting}>
                    Send Reset Link
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </form>
              </>
            ) : (
              <>
                <h1 className="font-display text-2xl font-bold tracking-tight">Check Your Email</h1>
                <p className="mt-2 text-muted-foreground">
                  If an account exists with that email, we've sent you a password reset link. 
                  Please check your inbox and spam folder.
                </p>
              </>
            )}

            <div className="mt-6">
              <Link
                to="/login"
                className="flex items-center gap-2 text-sm font-medium text-brand-700 hover:underline dark:text-brand-400"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Login
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
