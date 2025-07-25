'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { Amplify } from 'aws-amplify';
import { getCurrentUser, signIn, signOut, fetchAuthSession, signUp, confirmSignUp, resendSignUpCode } from 'aws-amplify/auth';
import amplifyConfig from '@/lib/amplify-config';

// Configure Amplify
Amplify.configure(amplifyConfig);

interface User {
  username: string;
  userId: string;
  email?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  signUp: (username: string, password: string, email: string) => Promise<{ nextStep: any }>;
  confirmSignUp: (username: string, confirmationCode: string) => Promise<void>;
  resendSignUpCode: (username: string) => Promise<void>;
  getAccessToken: () => Promise<string | null>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthState();
  }, []);

  const checkAuthState = async () => {
    try {
      const currentUser = await getCurrentUser();
      setUser({
        username: currentUser.username,
        userId: currentUser.userId,
        email: currentUser.signInDetails?.loginId
      });
    } catch (error) {
      console.log('User not authenticated');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSignIn = async (username: string, password: string) => {
    try {
      const result = await signIn({ username, password });
      if (result.isSignedIn) {
        await checkAuthState();
      }
    } catch (error) {
      console.error('Sign in error:', error);
      throw error;
    }
  };

  const handleSignOut = async () => {
    try {
      await signOut();
      setUser(null);
    } catch (error) {
      console.error('Sign out error:', error);
      throw error;
    }
  };

  const handleSignUp = async (username: string, password: string, email: string) => {
    try {
      const result = await signUp({
        username,
        password,
        options: {
          userAttributes: {
            email,
          },
        },
      });
      return result;
    } catch (error) {
      console.error('Sign up error:', error);
      throw error;
    }
  };

  const handleConfirmSignUp = async (username: string, confirmationCode: string) => {
    try {
      await confirmSignUp({ username, confirmationCode });
    } catch (error) {
      console.error('Confirm sign up error:', error);
      throw error;
    }
  };

  const handleResendSignUpCode = async (username: string) => {
    try {
      await resendSignUpCode({ username });
    } catch (error) {
      console.error('Resend sign up code error:', error);
      throw error;
    }
  };

  const getAccessToken = async (): Promise<string | null> => {
    try {
      const session = await fetchAuthSession();
      return session.tokens?.accessToken?.toString() || null;
    } catch (error) {
      console.error('Error fetching access token:', error);
      return null;
    }
  };

  const value: AuthContextType = {
    user,
    loading,
    signIn: handleSignIn,
    signOut: handleSignOut,
    signUp: handleSignUp,
    confirmSignUp: handleConfirmSignUp,
    resendSignUpCode: handleResendSignUpCode,
    getAccessToken,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};