import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowRight, Eye, EyeOff, Lock, Mail, MapPin, User as UserIcon } from 'lucide-react';

import { Brand } from '@/components/layout/Brand';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Form';
import { Alert } from '@/components/ui/Alert';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/contexts/ToastContext';
import { ApiError } from '@/services/api';

const schema = z
  .object({
    name: z
      .string()
      .min(2, 'Your name must be at least 2 characters.')
      .max(120, 'Your name is too long.'),
    email: z.string().min(1, 'Enter your email address.').email('Enter a valid email address.'),
    password: z
      .string()
      .min(8, 'Use at least 8 characters.')
      .max(128, 'The password is too long.')
      .regex(/[A-Za-z]/, 'Include at least one letter.')
      .regex(/\d/, 'Include at least one number.'),
    confirmPassword: z.string().min(1, 'Confirm your password.'),
    location: z.string().max(160, 'That location is too long.').optional(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: 'The two passwords do not match.',
    path: ['confirmPassword'],
  });

type RegisterForm = z.infer<typeof schema>;

export function RegisterPage() {
  const { register: createAccount } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      email: '',
      password: '',
      confirmPassword: '',
      location: '',
    },
  });

  const password = watch('password');

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const user = await createAccount({
        name: values.name,
        email: values.email,
        password: values.password,
        location: values.location?.trim() ? values.location.trim() : null,
      });
      toast.success(`Account created. Welcome, ${user.name.split(' ')[0]}!`);
      navigate('/dashboard', { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        const first = Object.values(caught.fieldErrors)[0];
        setServerError(first ?? caught.message);
      } else {
        setServerError(
          caught instanceof Error
            ? caught.message
            : 'Unable to create the account right now.',
        );
      }
    }
  });

  const strength = passwordScore(password);

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-20">
        <div className="mx-auto w-full max-w-md">
          <Brand className="mb-10" />

          <h1 className="font-display text-3xl font-bold tracking-tight">Join Agri-AI</h1>
          <p className="mt-2 text-muted-foreground">
            Start your smart farming journey with AI-powered insights.
          </p>

          {serverError ? (
            <Alert tone="danger" className="mt-6" title="Registration failed">
              {serverError}
            </Alert>
          ) : null}

          <form onSubmit={onSubmit} className="mt-8 space-y-5" noValidate>
            <Input
              label="Full name"
              autoComplete="name"
              placeholder="Ananya Sharma"
              icon={<UserIcon className="h-4 w-4" aria-hidden="true" />}
              error={errors.name?.message}
              {...register('name')}
            />

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
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
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

            {password ? (
              <div className="space-y-1.5">
                <div className="flex h-1.5 w-full gap-1">
                  {[0, 1, 2, 3].map((index) => (
                    <span
                      key={index}
                      className={`h-full flex-1 rounded-full transition-colors ${
                        index < strength.level
                          ? strength.barClass
                          : 'bg-muted'
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">Password strength: {strength.label}</p>
              </div>
            ) : null}

            <div className="space-y-1.5">
              <label htmlFor="confirmPassword" className="text-sm font-medium text-foreground">
                Confirm password
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  <Lock className="h-4 w-4" aria-hidden="true" />
                </span>
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Repeat your password"
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 pl-9 pr-10 text-sm text-foreground shadow-sm transition placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60"
                  {...register('confirmPassword')}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirmPassword?.message ? (
                <p className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                  {errors.confirmPassword?.message}
                </p>
              ) : null}
            </div>

            <Input
              label="Location (optional)"
              autoComplete="address-level2"
              placeholder="Nashik, Maharashtra"
              icon={<MapPin className="h-4 w-4" aria-hidden="true" />}
              hint="Used as the default location for weather lookups."
              error={errors.location?.message}
              {...register('location')}
            />

            <Button type="submit" size="lg" fullWidth isLoading={isSubmitting}>
              Create account
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link
              to="/login"
              className="focus-ring rounded font-medium text-brand-700 hover:underline dark:text-brand-400"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>

      <div className="relative hidden overflow-hidden bg-earth-950 lg:block">
        <div className="absolute inset-0 bg-grid-dark bg-grid-dark opacity-40" />
        <div className="relative flex h-full flex-col justify-center px-16 text-white">
          <p className="font-display text-3xl font-bold leading-tight">
            From a single leaf photo to a field-scale plan.
          </p>
          <ul className="mt-8 space-y-3 text-sm text-white/75">
            <li>• Classify 38 crop disease classes with a trained convolutional network</li>
            <li>• Rank 22 crops against your soil and climate readings</li>
            <li>• Estimate the harvest in tonnes per hectare</li>
            <li>• Pull live weather for your exact field</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function passwordScore(password: string): {
  level: number;
  label: string;
  barClass: string;
} {
  if (!password) return { level: 0, label: 'empty', barClass: '' };
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) && /[^\w\s]/.test(password)) score += 1;

  if (score <= 1) return { level: 1, label: 'weak', barClass: 'bg-red-500' };
  if (score === 2) return { level: 2, label: 'fair', barClass: 'bg-amber-500' };
  if (score === 3) return { level: 3, label: 'good', barClass: 'bg-lime-500' };
  return { level: 4, label: 'strong', barClass: 'bg-brand-500' };
}
