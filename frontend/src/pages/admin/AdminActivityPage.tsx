import { useState } from 'react';
import { ScrollText } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { SkeletonRows } from '@/components/ui/Spinner';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { Button } from '@/components/ui/Button';
import { useAsync } from '@/hooks/useAsync';
import { adminService } from '@/services';
import { formatDateTime } from '@/utils/format';

const PAGE_SIZE = 20;

export function AdminActivityPage() {
  const [page, setPage] = useState(1);

  const activity = useAsync(
    () => adminService.activity({ page, page_size: PAGE_SIZE }),
    [page],
  );

  const items = activity.data?.items ?? [];
  const pagination = activity.data?.pagination;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Administration"
        title="Audit trail"
        description="Every administrative action recorded by the server, newest first."
      />

      {activity.error ? (
        <ErrorState
          title="The audit trail could not be loaded"
          description={activity.error}
          onRetry={activity.reload}
        />
      ) : null}

      {activity.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <SkeletonRows rows={6} />
          </CardContent>
        </Card>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<ScrollText className="h-6 w-6" />}
          title="No audit events yet"
          description="Administrative actions such as role changes and account deletions are recorded here."
        />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recorded actions</CardTitle>
              <CardDescription>
                {pagination?.total ?? items.length} event
                {pagination?.total === 1 ? '' : 's'} in total.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Action</th>
                    <th className="py-2 pr-4 font-medium">Actor</th>
                    <th className="py-2 pr-4 font-medium">Target</th>
                    <th className="py-2 pr-4 font-medium">IP address</th>
                    <th className="py-2 font-medium">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="py-3 pr-4">
                        <Badge
                          tone={
                            item.action.includes('delete')
                              ? 'danger'
                              : item.action.includes('role')
                                ? 'earth'
                                : 'neutral'
                          }
                        >
                          {item.action}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {item.actor_email ?? 'system'}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {item.target_type ?? '—'}
                      </td>
                      <td className="py-3 pr-4 font-mono text-xs text-muted-foreground">
                        {item.ip_address ?? '—'}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {formatDateTime(item.created_at)}
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
    </PageContainer>
  );
}
