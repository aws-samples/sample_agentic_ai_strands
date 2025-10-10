"use client"

import { useState, useEffect } from 'react'
import { useTheme } from 'next-themes'
import ChatInterface from '@/components/chat/ChatInterface'
import Sidebar from '@/components/sidebar/sidebar'
import { ModeToggle } from '@/components/theme-toggle'
import { AuthGuard } from '@/components/auth/AuthGuard'
import { useAuth } from '@/components/providers/AuthProvider'
import { Settings, ChevronRight, LogOut, User } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function Home() {
  const [mounted, setMounted] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true) // Start with sidebar open
  const { theme } = useTheme()
  const { user, signOut } = useAuth()

  // Prevent hydration mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return null
  }

  const handleSignOut = async () => {
    try {
      await signOut()
    } catch (error) {
      console.error('Sign out error:', error)
    }
  }

  return (
    <AuthGuard>
      <main className="flex h-screen overflow-hidden">
        {/* Sidebar - push/pull style */}
        <div className={`
          transition-all duration-300 ease-in-out border-r border-border bg-card
          ${sidebarOpen ? 'w-80' : 'w-0'}
        `}>
          <div className={`
            h-full w-80 transition-opacity duration-300
            ${sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}
          `}>
            <Sidebar onClose={() => setSidebarOpen(false)} />
          </div>
        </div>

        {/* Main content - adjusts width based on sidebar */}
        <div className={`
          flex flex-col h-full transition-all duration-300 ease-in-out relative
          ${sidebarOpen ? 'flex-1' : 'w-full'}
        `}>
          {/* Floating expand button when sidebar is closed */}
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="fixed left-4 top-20 z-50 p-3 bg-primary text-primary-foreground rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105"
              title="Open Settings"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          )}

          {/* Header */}
          <header className="h-14 border-b border-border flex items-center justify-between px-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex items-center gap-3">
              {sidebarOpen && (
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="p-2 rounded-md hover:bg-secondary transition-colors"
                  title="Close Settings"
                >
                  <Settings className="h-5 w-5" />
                </button>
              )}
              <h1 className="text-lg font-semibold"> Claude Agent in Bedrock AgentCore</h1>
            </div>
            <div className="flex items-center gap-2">
              {user && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <User className="h-4 w-4" />
                  <span>{user.username}</span>
                </div>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSignOut}
                className="text-muted-foreground hover:text-foreground"
                title="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </Button>
              <ModeToggle />
            </div>
          </header>

          {/* Chat interface - adjusts to available space */}
          <div className="flex-1 overflow-hidden">
            <ChatInterface />
          </div>
        </div>
      </main>
    </AuthGuard>
  )
}
