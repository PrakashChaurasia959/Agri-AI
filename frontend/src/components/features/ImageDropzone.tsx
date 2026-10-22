import { useCallback, useRef, useState, type DragEvent } from 'react';
import { Image as ImageIcon, Upload, X } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';
import { ACCEPTED_IMAGE_TYPES, MAX_UPLOAD_MB } from '@/utils/constants';

export interface ImageDropzoneProps {
  file: File | null;
  onFile: (file: File | null) => void;
  disabled?: boolean;
  className?: string;
}

const MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

export function ImageDropzone({
  file,
  onFile,
  disabled = false,
  className,
}: ImageDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const accept = useCallback(
    (candidate: File | undefined) => {
      if (!candidate) return;
      if (!ACCEPTED_IMAGE_TYPES.includes(candidate.type)) {
        setError('Only JPEG, PNG and WebP images are accepted.');
        return;
      }
      if (candidate.size > MAX_BYTES) {
        setError(`The image is larger than ${MAX_UPLOAD_MB} MB.`);
        return;
      }
      setError(null);
      onFile(candidate);
      const reader = new FileReader();
      reader.onload = () => setPreview(typeof reader.result === 'string' ? reader.result : null);
      reader.readAsDataURL(candidate);
    },
    [onFile],
  );

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    accept(event.dataTransfer.files?.[0]);
  };

  const clear = () => {
    onFile(null);
    setPreview(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  if (file && preview) {
    return (
      <div className={cn('relative overflow-hidden rounded-2xl border border-border', className)}>
        <img
          src={preview}
          alt="The leaf image you selected"
          className="max-h-[420px] w-full object-contain bg-muted"
        />
        <div className="absolute right-3 top-3 flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={clear}
            disabled={disabled}
            className="bg-background/90 backdrop-blur"
          >
            <X className="h-4 w-4" aria-hidden="true" />
            Remove
          </Button>
        </div>
        <p className="border-t border-border bg-card/80 px-4 py-2 text-xs text-muted-foreground backdrop-blur">
          {file.name} · {(file.size / 1024).toFixed(0)} KB
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-12 text-center transition',
          dragging
            ? 'border-brand-500 bg-brand-500/5'
            : 'border-border bg-card/40 hover:border-brand-400/60 hover:bg-card',
          disabled && 'pointer-events-none opacity-60',
        )}
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-400">
          <ImageIcon className="h-7 w-7" aria-hidden="true" />
        </div>
        <div className="space-y-1">
          <p className="font-display text-base font-semibold">Upload a leaf photo</p>
          <p className="text-sm text-muted-foreground">
            Drag an image here, or choose a file. JPEG, PNG or WebP, up to {MAX_UPLOAD_MB} MB.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
        >
          <Upload className="h-4 w-4" aria-hidden="true" />
          Choose a file
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_IMAGE_TYPES.join(',')}
          className="sr-only"
          onChange={(event) => accept(event.target.files?.[0])}
          aria-label="Leaf image"
        />
      </div>
      {error ? (
        <p className="mt-2 text-xs font-medium text-red-600 dark:text-red-400">{error}</p>
      ) : null}
    </div>
  );
}
