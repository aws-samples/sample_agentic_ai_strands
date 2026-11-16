import { ChatProvider } from '@/components/providers/ChatProvider'
import { AuthGate } from '@/components/providers/AuthGate'

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AuthGate>
      <ChatProvider>
        {children}
      </ChatProvider>
    </AuthGate>
  )
}
