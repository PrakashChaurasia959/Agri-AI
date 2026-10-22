import { useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { LogOut, Menu, Moon, Sun, X } from 'lucide-react';

import { Brand } from './Brand';
import { Button, IconButton } from '@/components/ui/Button';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { cn } from '@/utils/cn';
import { ADMIN_NAV, PRIMARY_NAV } from '@/utils/constants';

export function Navbar() {
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  const navItems = isAdmin ? [...PRIMARY_NAV, ...ADMIN_NAV] : PRIMARY_NAV;

  const links = (
    <>
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={() => setMenuOpen(false)}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              isActive
                ? 'bg-brand-500/12 text-brand-700 dark:text-brand-300'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )
          }
        >
          <item.icon className="h-4 w-4" aria-hidden="true" />
          {item.label}
        </NavLink>
      ))}
    </>
  );

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Brand />

        <nav className="ml-4 hidden items-center gap-1 lg:flex" aria-label="Main navigation">
          {links}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <IconButton
            label={isDark ? 'Switch to the light theme' : 'Switch to the dark theme'}
            onClick={toggleTheme}
          >
            {isDark ? (
              <Sun className="h-4.5 w-4.5" aria-hidden="true" />
            ) : (
              <Moon className="h-4.5 w-4.5" aria-hidden="true" />
            )}
          </IconButton>

          {isAuthenticated ? (
            <>
              <Link
                to="/profile"
                className="focus-ring hidden items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground sm:flex"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
                  {user?.name?.charAt(0).toUpperCase() ?? 'U'}
                </span>
                {user?.name}
              </Link>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void logout();
                }}
                className="hidden sm:inline-flex"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Sign out
              </Button>
            </>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Link
                to="/login"
                className="focus-ring inline-flex h-10 items-center justify-center rounded-lg px-4 text-sm font-medium text-foreground transition hover:bg-muted"
              >
                Sign in
              </Link>
              <Link
                to="/register"
                className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
              >
                Get started
              </Link>
            </div>
          )}

          <IconButton
            label={menuOpen ? 'Close the menu' : 'Open the menu'}
            className="lg:hidden"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
          >
            {menuOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </IconButton>
        </div>
      </div>

      {menuOpen ? (
        <div className="border-t border-border bg-card/95 px-4 py-3 backdrop-blur-xl lg:hidden">
          <nav className="flex flex-col gap-1" aria-label="Mobile navigation">
            {links}
          </nav>
          <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
            {isAuthenticated ? (
              <>
                <Link
                  to="/profile"
                  className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
                >
                  My profile
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setMenuOpen(false);
                    void logout();
                  }}
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  Sign out
                </Button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="focus-ring inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium transition hover:bg-muted"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
                >
                  Create an account
                </Link>
              </>
            )}
          </div>
        </div>
      ) : null}

      {location.pathname === '/' ? null : null}
    </header>
  );
}
