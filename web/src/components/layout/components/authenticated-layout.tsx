/*
Copyright (C) 2023-2026 QuantumNous

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

For commercial licensing, please contact support@quantumnous.com
*/
import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'

import { CommandMenu } from '@/components/command-menu'
import { AnimatedOutlet } from '@/components/page-transition'
import { SkipToMain } from '@/components/skip-to-main'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { LayoutProvider } from '@/context/layout-provider'
import { SearchProvider } from '@/context/search-provider'
import { ChangePasswordDialog } from '@/features/security/components/dialogs/change-password-dialog'
import { getSelf } from '@/lib/api'
import { getCookie } from '@/lib/cookies'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'

import { AppHeader } from './app-header'
import { AppSidebar } from './app-sidebar'

type AuthenticatedLayoutProps = {
  children?: React.ReactNode
}

export function AuthenticatedLayout(props: AuthenticatedLayoutProps) {
  const { t } = useTranslation()
  const defaultOpen = getCookie('sidebar_state') !== 'false'
  const signedIn = useAuthStore((s) => !!s.auth.user)
  const user = useAuthStore((s) => s.auth.user)
  const setUser = useAuthStore((s) => s.auth.setUser)
  // Unmount pages on sign-out, otherwise their queries refetch and toast "Session expired!" / "invalid access token"
  const refreshSelf = useCallback(async () => {
    try {
      const response = await getSelf()
      if (response.success && response.data) {
        setUser(response.data)
      }
    } catch {
      // Session rotation on password change already refreshed the store.
    }
  }, [setUser])

  if (!signedIn) return null

  // 首次登录强制改密：服务端已拦截除改密外的全部 API；这里只负责把页面收进改密弹窗，
  // 避免被拦页面触发成串错误提示。改密成功后 flag 由 /api/user/self 刷新清除。
  if (user?.must_change_password) {
    return (
      <LayoutProvider>
        <div className='bg-background flex min-h-svh flex-col items-center justify-center gap-3 p-6 text-center'>
          <p className='text-foreground text-lg font-semibold'>
            {t('You must change your password before continuing')}
          </p>
          <p className='text-muted-foreground max-w-md text-sm'>
            {t(
              'Your account still uses the initial password. Set a new one to unlock the console.'
            )}
          </p>
        </div>
        <ChangePasswordDialog
          open
          onOpenChange={() => {}}
          username={user.username ?? ''}
          onSuccess={refreshSelf}
        />
      </LayoutProvider>
    )
  }

  return (
    <LayoutProvider>
      <SearchProvider>
        <SidebarProvider defaultOpen={defaultOpen} className='flex-col'>
          <SkipToMain />
          <AppHeader />
          <div className='flex min-h-0 w-full flex-1'>
            <AppSidebar />
            <SidebarInset
              className={cn(
                '@container/content',
                'h-[calc(100svh-var(--app-header-height,0px))]',
                'min-h-0 overflow-hidden',
                'peer-data-[variant=inset]:h-[calc(100svh-var(--app-header-height,0px)-(var(--spacing)*4))]'
              )}
            >
              {props.children ?? <AnimatedOutlet />}
            </SidebarInset>
          </div>
        </SidebarProvider>
        <CommandMenu />
      </SearchProvider>
    </LayoutProvider>
  )
}
