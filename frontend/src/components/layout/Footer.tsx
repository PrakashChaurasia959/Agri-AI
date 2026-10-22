import { Link } from 'react-router-dom';

import { Brand } from './Brand';

export function Footer() {
  return (
    <footer className="border-t border-border bg-card/40">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
        <div className="space-y-1">
          <Brand />
          <p className="max-w-md text-xs text-muted-foreground">
            AgriVision AI is a final-year engineering project. Its predictions are
            decision support, not a laboratory diagnosis - always confirm with a
            qualified agronomist before acting on them.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
          <Link
            to="/dashboard"
            className="focus-ring rounded transition hover:text-foreground"
          >
            Dashboard
          </Link>
          <Link to="/disease" className="focus-ring rounded transition hover:text-foreground">
            Disease detection
          </Link>
          <Link to="/crops" className="focus-ring rounded transition hover:text-foreground">
            Crop recommendation
          </Link>
          <a
            href="/docs"
            className="focus-ring rounded transition hover:text-foreground"
            target="_blank"
            rel="noreferrer"
          >
            API documentation
          </a>
        </div>
      </div>
      <div className="border-t border-border/70 px-4 py-4 text-center text-[11px] text-muted-foreground sm:px-6 lg:px-8">
        Built with FastAPI, MongoDB, TensorFlow and React. Weather data by Open-Meteo.
      </div>
    </footer>
  );
}
