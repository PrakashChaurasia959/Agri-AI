import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { KeyRound, MapPin, Save, Shield, User as UserIcon } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Textarea } from '@/components/ui/Form';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/contexts/ToastContext';
import { authService } from '@/services/auth';
import { formatDateTime } from '@/utils/format';

const profileSchema = z.object({
  name: z
    .string()
    .min(2, 'Your name must be at least 2 characters.')
    .max(120, 'Your name is too long.'),
  location: z.string().max(160, 'That location is too long.'),
  farm_size_hectares: z
    .string()
    .refine(
      (value) =>
        value.trim() === '' ||
        (!Number.isNaN(Number(value)) &&
          Number(value) >= 0 &&
          Number(value) <= 1_000_000),
      { message: 'Enter a number between 0 and 1,000,000.' },
    ),
  primary_crops: z.string().max(1500, 'That list is too long.'),
});

type ProfileForm = z.infer<typeof profileSchema>;

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password.'),
    new_password: z
      .string()
      .min(8, 'Use at least 8 characters.')
      .max(128, 'The password is too long.')
      .regex(/[A-Za-z]/, 'Include at least one letter.')
      .regex(/\d/, 'Include at least one number.'),
    confirm_password: z.string().min(1, 'Confirm the new password.'),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: 'The two passwords do not match.',
    path: ['confirm_password'],
  });

type PasswordForm = z.infer<typeof passwordSchema>;

export function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();

  const [profileSaved, setProfileSaved] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);

  const {
    register: registerProfile,
    handleSubmit: submitProfile,
    reset: resetProfile,
    formState: { errors: profileErrors, isSubmitting: savingProfile },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: '',
      location: '',
      farm_size_hectares: '',
      primary_crops: '',
    },
  });

  const {
    register: registerPassword,
    handleSubmit: submitPassword,
    reset: resetPassword,
    formState: { errors: passwordErrors, isSubmitting: savingPassword },
  } = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
  });

  useEffect(() => {
    if (!user) return;
    resetProfile({
      name: user.name,
      location: user.location ?? '',
      farm_size_hectares:
        user.farm_size_hectares === null ? '' : String(user.farm_size_hectares),
      primary_crops: user.primary_crops.join(', '),
    });
  }, [user, resetProfile]);

  const onProfileSubmit = submitProfile(async (values) => {
    setProfileSaved(false);
    try {
      await authService.updateProfile({
        name: values.name,
        location: values.location.trim() ? values.location.trim() : null,
        farm_size_hectares:
          values.farm_size_hectares === '' ? null : Number(values.farm_size_hectares),
        primary_crops: values.primary_crops
          .split(',')
          .map((crop) => crop.trim())
          .filter(Boolean),
      });
      await refreshUser();
      setProfileSaved(true);
      toast.success('Your profile was updated.');
    } catch (caught) {
      toast.error(
        'The profile could not be saved',
        caught instanceof Error ? caught.message : undefined,
      );
    }
  });

  const onPasswordSubmit = submitPassword(async (values) => {
    setPasswordSaved(false);
    try {
      await authService.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      resetPassword();
      setPasswordSaved(true);
      toast.success('Your password was changed.');
    } catch (caught) {
      toast.error(
        'The password could not be changed',
        caught instanceof Error ? caught.message : undefined,
      );
    }
  });

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Profile"
        title="Your account"
        description="Keep the details that describe your farm up to date. They are stored on your own account and are never shared with other users."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserIcon className="h-4 w-4 text-brand-600" aria-hidden="true" />
                Farm details
              </CardTitle>
              <CardDescription>
                The location and crop list are used as defaults across the platform.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onProfileSubmit} className="space-y-5" noValidate>
                <Input
                  label="Full name"
                  error={profileErrors.name?.message}
                  {...registerProfile('name')}
                />
                <Input
                  label="Location"
                  placeholder="Nashik, Maharashtra"
                  icon={<MapPin className="h-4 w-4" aria-hidden="true" />}
                  error={profileErrors.location?.message}
                  {...registerProfile('location')}
                />
                <Input
                  label="Farm size"
                  type="number"
                  step="any"
                  hint="hectares - optional"
                  error={profileErrors.farm_size_hectares?.message}
                  {...registerProfile('farm_size_hectares')}
                />
                <Textarea
                  label="Primary crops"
                  placeholder="rice, wheat, cotton"
                  hint="Separate the crops with commas."
                  error={profileErrors.primary_crops?.message}
                  {...registerProfile('primary_crops')}
                />

                {profileSaved ? (
                  <Alert tone="success" title="Profile saved">
                    Your details were updated successfully.
                  </Alert>
                ) : null}

                <Button type="submit" isLoading={savingProfile}>
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Save changes
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-earth-600" aria-hidden="true" />
                Change password
              </CardTitle>
              <CardDescription>
                The password is stored as an Argon2id hash and is never recoverable.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onPasswordSubmit} className="space-y-5" noValidate>
                <Input
                  label="Current password"
                  type="password"
                  autoComplete="current-password"
                  error={passwordErrors.current_password?.message}
                  {...registerPassword('current_password')}
                />
                <Input
                  label="New password"
                  type="password"
                  autoComplete="new-password"
                  hint="At least 8 characters, with a letter and a number."
                  error={passwordErrors.new_password?.message}
                  {...registerPassword('new_password')}
                />
                <Input
                  label="Confirm new password"
                  type="password"
                  autoComplete="new-password"
                  error={passwordErrors.confirm_password?.message}
                  {...registerPassword('confirm_password')}
                />

                {passwordSaved ? (
                  <Alert tone="success" title="Password changed">
                    Use your new password the next time you sign in.
                  </Alert>
                ) : null}

                <Button type="submit" variant="secondary" isLoading={savingPassword}>
                  <KeyRound className="h-4 w-4" aria-hidden="true" />
                  Update password
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Account</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-600 font-display text-2xl font-bold text-white">
                {user?.name?.charAt(0).toUpperCase() ?? 'U'}
              </div>
              <div className="space-y-1">
                <p className="font-display text-base font-semibold">{user?.name}</p>
                <p className="text-sm text-muted-foreground">{user?.email}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge
                  tone={user?.role === 'admin' ? 'earth' : 'brand'}
                  icon={<Shield className="h-3.5 w-3.5" />}
                >
                  {user?.role === 'admin' ? 'Administrator' : 'Farmer'}
                </Badge>
              </div>
              <dl className="space-y-2 border-t border-border pt-4 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Member since</dt>
                  <dd className="font-medium">{formatDateTime(user?.created_at)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Last sign-in</dt>
                  <dd className="font-medium">{formatDateTime(user?.last_login_at)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Farm size</dt>
                  <dd className="font-medium">
                    {user?.farm_size_hectares !== null && user?.farm_size_hectares !== undefined
                      ? `${user.farm_size_hectares} ha`
                      : '—'}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">How your data is handled</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
                <li>Your password is hashed with Argon2id and is never stored in plain text.</li>
                <li>The session lives in an HttpOnly cookie, so scripts cannot read it.</li>
                <li>Uploaded images are analysed in memory; only the metadata is stored.</li>
                <li>Other users can never see your predictions - the API checks ownership.</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
