/*
Copyright (C) 2023-2026 QuantumNous

This program is licensed under the GNU Affero General Public License as
published by the Free Software Foundation. See the LICENSE file for details.
*/
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DirectionProvider } from '@/context/direction-provider'
import { useAuthStore } from '@/stores/auth-store'

import { AuthenticatedLayout } from '../authenticated-layout'

vi.mock(
  '@/features/security/components/dialogs/change-password-dialog',
  () => ({
    ChangePasswordDialog: (props: { open: boolean; username: string }) => (
      <div data-testid='change-password-dialog'>
        open={String(props.open)} username={props.username}
      </div>
    ),
  })
)

vi.mock('@/lib/api', () => ({
  getSelf: vi.fn(async () => ({ success: true, data: {} })),
}))

function signIn(mustChangePassword?: boolean) {
  useAuthStore.getState().auth.setUser({
    id: 1,
    username: 'gate-user',
    role: 1,
    must_change_password: mustChangePassword,
  })
}

let client: QueryClient

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})

async function renderLayout(children: React.ReactNode) {
  const router = createRouter({
    routeTree: createRootRoute({
      component: () => (
        <DirectionProvider>
          <QueryClientProvider client={client}>{children}</QueryClientProvider>
        </DirectionProvider>
      ),
    }),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  await router.load()
  return render(<RouterProvider router={router} />)
}

afterEach(() => {
  cleanup()
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

describe('authenticated layout password gate', () => {
  it('locks the console behind the change-password dialog while the flag is set', async () => {
    signIn(true)
    await renderLayout(
      <AuthenticatedLayout>
        <div data-testid='console-page'>page</div>
      </AuthenticatedLayout>
    )
    expect(screen.getByTestId('change-password-dialog')).toHaveTextContent(
      'open=true username=gate-user'
    )
    expect(screen.queryByTestId('console-page')).not.toBeInTheDocument()
  })

  it('renders the console normally once the flag is cleared', async () => {
    signIn(false)
    await renderLayout(
      <AuthenticatedLayout>
        <div data-testid='console-page'>page</div>
      </AuthenticatedLayout>
    )
    expect(
      screen.queryByTestId('change-password-dialog')
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('console-page')).toBeVisible()
  })
})
