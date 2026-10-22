import { useState } from 'react';
import { Search, ShieldCheck, Trash2, UserCog } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Form';
import { Badge } from '@/components/ui/Badge';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonRows } from '@/components/ui/Spinner';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { useAsync } from '@/hooks/useAsync';
import { useDebounced } from '@/hooks/useDebounced';
import { adminService } from '@/services';
import { useToast } from '@/contexts/ToastContext';
import { formatDateTime } from '@/utils/format';
import type { AdminUser } from '@/types';

const ROLE_FILTERS = [
  { id: 'all', label: 'All roles' },
  { id: 'user', label: 'Users' },
  { id: 'admin', label: 'Admins' },
];

const PAGE_SIZE = 15;

export function AdminUsersPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('all');
  const [page, setPage] = useState(1);
  const [pending, setPending] = useState<AdminUser | null>(null);
  const [isWorking, setIsWorking] = useState(false);

  const debouncedSearch = useDebounced(search, 350);

  const users = useAsync(
    () =>
      adminService.users({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch.trim() || undefined,
        role: role === 'all' ? undefined : role,
      }),
    [page, role, debouncedSearch],
  );

  const changeRole = async (user: AdminUser, nextRole: 'user' | 'admin') => {
    setIsWorking(true);
    try {
      await adminService.setRole(user.id, nextRole);
      toast.success(
        `${user.name} is now ${nextRole === 'admin' ? 'an administrator' : 'a standard user'}.`,
      );
      users.reload();
    } catch (caught) {
      toast.error(
        'The role could not be changed',
        caught instanceof Error ? caught.message : undefined,
      );
    } finally {
      setIsWorking(false);
    }
  };

  const confirmDelete = async () => {
    if (!pending) return;
    setIsWorking(true);
    try {
      await adminService.remove(pending.id);
      toast.success('The account and its records were deleted.');
      setPending(null);
      users.reload();
    } catch (caught) {
      toast.error(
        'The account could not be deleted',
        caught instanceof Error ? caught.message : undefined,
      );
    } finally {
      setIsWorking(false);
    }
  };

  const items = users.data?.items ?? [];
  const pagination = users.data?.pagination;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Administration"
        title="Users"
        description="Every account on the platform, with the number of predictions each one has made."
      />

      <Card className="mb-6">
        <CardContent className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <Tabs
            items={ROLE_FILTERS.map((item) => ({ id: item.id, label: item.label }))}
            active={role}
            onChange={(id) => {
              setRole(id);
              setPage(1);
            }}
          />
          <div className="lg:w-72">
            <Input
              placeholder="Search by name or email…"
              icon={<Search className="h-4 w-4" aria-hidden="true" />}
              aria-label="Search users"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </div>
        </CardContent>
      </Card>

      {users.error ? (
        <ErrorState
          title="The user list could not be loaded"
          description={users.error}
          onRetry={users.reload}
        />
      ) : null}

      {users.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <SkeletonRows rows={6} />
          </CardContent>
        </Card>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<ShieldCheck className="h-6 w-6" />}
          title="No matching users"
          description="Try a different search term or role filter."
        />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Accounts</CardTitle>
              <CardDescription>
                {pagination?.total ?? items.length} account
                {pagination?.total === 1 ? '' : 's'} in total.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">User</th>
                    <th className="py-2 pr-4 font-medium">Role</th>
                    <th className="py-2 pr-4 font-medium">Predictions</th>
                    <th className="py-2 pr-4 font-medium">Joined</th>
                    <th className="py-2 pr-4 font-medium">Last sign-in</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {items.map((user) => (
                    <tr key={user.id}>
                      <td className="py-3 pr-4">
                        <p className="font-medium">{user.name}</p>
                        <p className="text-xs text-muted-foreground">{user.email}</p>
                      </td>
                      <td className="py-3 pr-4">
                        <Badge tone={user.role === 'admin' ? 'earth' : 'neutral'}>
                          {user.role}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 tabular-nums">{user.total_predictions}</td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {formatDateTime(user.created_at)}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {formatDateTime(user.last_login_at)}
                      </td>
                      <td className="py-3">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={isWorking}
                            onClick={() =>
                              void changeRole(user, user.role === 'admin' ? 'user' : 'admin')
                            }
                          >
                            <UserCog className="h-4 w-4" aria-hidden="true" />
                            {user.role === 'admin' ? 'Demote' : 'Promote'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Delete ${user.name}`}
                            disabled={isWorking}
                            onClick={() => setPending(user)}
                          >
                            <Trash2 className="h-4 w-4 text-red-600" aria-hidden="true" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {pagination && pagination.total_pages > 1 ? (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Page {pagination.page} of {pagination.total_pages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!pagination.has_previous}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!pagination.has_next}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </>
      )}

      <Modal
        open={pending !== null}
        onClose={() => setPending(null)}
        title="Delete this account?"
        description="The user, their predictions, their crop records and their saved reports will all be removed permanently."
        footer={
          <>
            <Button variant="outline" onClick={() => setPending(null)}>
              Cancel
            </Button>
            <Button variant="danger" isLoading={isWorking} onClick={() => void confirmDelete()}>
              Delete account
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted-foreground">
          {pending ? `“${pending.name}” (${pending.email}) will be deleted.` : ''}
        </p>
      </Modal>
    </PageContainer>
  );
}
