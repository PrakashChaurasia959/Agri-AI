import { useState } from 'react';
import { Link } from 'react-router-dom';
import { History, Leaf, Search, Sprout, Trash2, TrendingUp } from 'lucide-react';

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
import { historyService } from '@/services/history';
import { useToast } from '@/contexts/ToastContext';
import { formatDateTime, formatPercent, humaniseClassName } from '@/utils/format';
import type { PredictionListItem } from '@/types';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'disease', label: 'Disease' },
  { id: 'crop_recommendation', label: 'Crops' },
  { id: 'yield', label: 'Yield' },
];

const PAGE_SIZE = 12;

export function HistoryPage() {
  const toast = useToast();
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<PredictionListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const debouncedSearch = useDebounced(search, 350);

  const history = useAsync(
    () =>
      historyService.list({
        page,
        page_size: PAGE_SIZE,
        prediction_type: filter === 'all' ? undefined : filter,
        search: debouncedSearch.trim() || undefined,
      }),
    [page, filter, debouncedSearch],
  );

  const items = history.data?.items ?? [];
  const pagination = history.data?.pagination;

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setIsDeleting(true);
    try {
      await historyService.remove(pendingDelete.id);
      toast.success('The record was deleted.');
      setPendingDelete(null);
      history.reload();
    } catch (caught) {
      toast.error(
        'Could not delete the record',
        caught instanceof Error ? caught.message : undefined,
      );
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <PageContainer>
      <PageHeader
        eyebrow="History"
        title="Every prediction you have made"
        description="A complete, searchable record of the analyses you have run on your account."
        actions={
          <Link
            to="/disease"
            className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
          >
            New analysis
          </Link>
        }
      />

      <Card className="mb-6">
        <CardContent className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <Tabs
            items={FILTERS.map((item) => ({ id: item.id, label: item.label }))}
            active={filter}
            onChange={(id) => {
              setFilter(id);
              setPage(1);
            }}
          />
          <div className="lg:w-72">
            <Input
              placeholder="Search by class name…"
              icon={<Search className="h-4 w-4" aria-hidden="true" />}
              aria-label="Search history"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </div>
        </CardContent>
      </Card>

      {history.error ? (
        <ErrorState
          title="The history could not be loaded"
          description={history.error}
          onRetry={history.reload}
        />
      ) : null}

      {history.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <SkeletonRows rows={6} />
          </CardContent>
        </Card>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<History className="h-6 w-6" />}
          title={search || filter !== 'all' ? 'No matching records' : 'Your history is empty'}
          description={
            search || filter !== 'all'
              ? 'Try a different search term or switch back to the "All" filter.'
              : 'Run a disease detection, a crop recommendation or a yield estimate and it will show up here.'
          }
          action={
            <Link
              to="/disease"
              className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white transition hover:bg-brand-700"
            >
              Detect a disease
            </Link>
          }
        />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Saved predictions</CardTitle>
              <CardDescription>
                {pagination?.total ?? items.length} record
                {pagination?.total === 1 ? '' : 's'} in total.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Prediction</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Confidence</th>
                    <th className="py-2 pr-4 font-medium">Model</th>
                    <th className="py-2 pr-4 font-medium">Created</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-3">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                            {item.prediction_type === 'disease' ? (
                              <Leaf className="h-4 w-4 text-brand-600" aria-hidden="true" />
                            ) : item.prediction_type === 'crop_recommendation' ? (
                              <Sprout className="h-4 w-4 text-earth-600" aria-hidden="true" />
                            ) : (
                              <TrendingUp className="h-4 w-4 text-sky-600" aria-hidden="true" />
                            )}
                          </span>
                          <span className="font-medium">
                            {humaniseClassName(item.predicted_class)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {item.prediction_type.replace(/_/g, ' ')}
                      </td>
                      <td className="py-3 pr-4">
                        {item.confidence === null ? (
                          <Badge tone="neutral">estimate</Badge>
                        ) : (
                          <Badge
                            tone={
                              item.confidence >= 0.8
                                ? 'success'
                                : item.confidence >= 0.5
                                  ? 'warning'
                                  : 'danger'
                            }
                          >
                            {formatPercent(item.confidence)}
                          </Badge>
                        )}
                      </td>
                      <td className="py-3 pr-4 text-xs text-muted-foreground">
                        {item.model_name} v{item.model_version}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {formatDateTime(item.created_at)}
                      </td>
                      <td className="py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label="Delete this prediction"
                          onClick={() => setPendingDelete(item)}
                        >
                          <Trash2 className="h-4 w-4 text-red-600" aria-hidden="true" />
                        </Button>
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
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete this prediction?"
        description="The record and its stored details will be removed permanently. This cannot be undone."
        footer={
          <>
            <Button variant="outline" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" isLoading={isDeleting} onClick={() => void confirmDelete()}>
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted-foreground">
          {pendingDelete
            ? `“${humaniseClassName(pendingDelete.predicted_class)}” will be removed from your history.`
            : ''}
        </p>
      </Modal>
    </PageContainer>
  );
}
