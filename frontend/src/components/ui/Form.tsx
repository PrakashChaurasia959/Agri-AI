import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';
import { AlertCircle } from 'lucide-react';

import { cn } from '@/utils/cn';

const CONTROL_CLASSES =
  'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm transition ' +
  'placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ' +
  'focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-[invalid=true]:border-red-500 aria-[invalid=true]:ring-red-500/40';

export interface FieldProps {
  label?: string;
  hint?: string;
  error?: string | null;
  required?: boolean;
  children: (props: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
  className?: string;
}

export function Field({ label, hint, error, required, children, className }: FieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy =
    [error ? errorId : null, hint && !error ? hintId : null].filter(Boolean).join(' ') ||
    undefined;

  return (
    <div className={cn('space-y-1.5', className)}>
      {label ? (
        <label htmlFor={id} className="text-sm font-medium text-foreground">
          {label}
          {required ? <span className="ml-0.5 text-red-500">*</span> : null}
        </label>
      ) : null}
      {children({ id, describedBy, invalid: Boolean(error) })}
      {error ? (
        <p id={errorId} className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
          <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string | null;
  icon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, icon, className, id, ...props },
  ref,
) {
  return (
    <Field label={label} hint={hint} error={error} required={props.required}>
      {({ id: fieldId, describedBy, invalid }) => (
        <div className="relative">
          {icon ? (
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              {icon}
            </span>
          ) : null}
          <input
            ref={ref}
            id={id ?? fieldId}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={cn(CONTROL_CLASSES, icon && 'pl-9', className)}
            {...props}
          />
        </div>
      )}
    </Field>
  );
});

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string | null;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, className, id, children, ...props },
  ref,
) {
  return (
    <Field label={label} hint={hint} error={error} required={props.required}>
      {({ id: fieldId, describedBy, invalid }) => (
        <select
          ref={ref}
          id={id ?? fieldId}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cn(CONTROL_CLASSES, 'cursor-pointer pr-8', className)}
          {...props}
        >
          {children}
        </select>
      )}
    </Field>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string | null;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, id, ...props },
  ref,
) {
  return (
    <Field label={label} hint={hint} error={error} required={props.required}>
      {({ id: fieldId, describedBy, invalid }) => (
        <textarea
          ref={ref}
          id={id ?? fieldId}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cn(CONTROL_CLASSES, 'min-h-[96px] resize-y', className)}
          {...props}
        />
      )}
    </Field>
  );
});
