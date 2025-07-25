'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/providers/AuthProvider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Eye, EyeOff, ArrowLeft } from 'lucide-react';

interface RegisterFormProps {
  onSuccess?: () => void;
}

type RegisterStep = 'register' | 'confirm';

export const RegisterForm: React.FC<RegisterFormProps> = ({ onSuccess }) => {
  const { signUp, confirmSignUp, resendSignUpCode } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState<RegisterStep>('register');
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    confirmationCode: ''
  });
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateRegisterForm = () => {
    const newErrors: { [key: string]: string } = {};
    
    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (formData.username.length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    }
    
    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }
    
    if (!formData.password.trim()) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/.test(formData.password)) {
      newErrors.password = 'Password must contain uppercase, lowercase, number, and special character';
    }
    
    if (!formData.confirmPassword.trim()) {
      newErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateConfirmForm = () => {
    const newErrors: { [key: string]: string } = {};
    
    if (!formData.confirmationCode.trim()) {
      newErrors.confirmationCode = 'Confirmation code is required';
    } else if (formData.confirmationCode.length !== 6) {
      newErrors.confirmationCode = 'Confirmation code must be 6 digits';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateRegisterForm()) return;
    
    setIsSubmitting(true);
    setErrors({});
    
    try {
      const result = await signUp(formData.username, formData.password, formData.email);
      
      if (result.nextStep?.signUpStep === 'CONFIRM_SIGN_UP') {
        setStep('confirm');
      } else {
        // Handle other next steps if needed
        onSuccess?.();
      }
    } catch (error: any) {
      console.error('Registration failed:', error);
      
      let errorMessage = 'Registration failed. Please try again.';
      
      if (error.name === 'UsernameExistsException') {
        errorMessage = 'Username already exists. Please choose a different username.';
      } else if (error.name === 'InvalidPasswordException') {
        errorMessage = 'Password does not meet requirements.';
      } else if (error.name === 'InvalidParameterException') {
        errorMessage = 'Invalid email format.';
      } else if (error.name === 'TooManyRequestsException') {
        errorMessage = 'Too many requests. Please try again later.';
      }
      
      setErrors({ general: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmRegistration = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateConfirmForm()) return;
    
    setIsSubmitting(true);
    setErrors({});
    
    try {
      await confirmSignUp(formData.username, formData.confirmationCode);
      onSuccess?.();
    } catch (error: any) {
      console.error('Confirmation failed:', error);
      
      let errorMessage = 'Confirmation failed. Please try again.';
      
      if (error.name === 'CodeMismatchException') {
        errorMessage = 'Invalid confirmation code. Please check and try again.';
      } else if (error.name === 'ExpiredCodeException') {
        errorMessage = 'Confirmation code has expired. Please request a new code.';
      } else if (error.name === 'NotAuthorizedException') {
        errorMessage = 'User is already confirmed or code is invalid.';
      }
      
      setErrors({ general: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendCode = async () => {
    setIsSubmitting(true);
    setErrors({});
    
    try {
      await resendSignUpCode(formData.username);
      setErrors({ success: 'New confirmation code sent to your email.' });
    } catch (error: any) {
      console.error('Resend code failed:', error);
      
      let errorMessage = 'Failed to resend code. Please try again.';
      
      if (error.name === 'NotAuthorizedException' && error.message.includes('Auto verification not turned on')) {
        errorMessage = 'Code resend is not available. Please contact support or try registering again.';
      } else if (error.name === 'TooManyRequestsException') {
        errorMessage = 'Too many requests. Please wait before trying again.';
      } else if (error.name === 'UserNotFoundException') {
        errorMessage = 'User not found. Please try registering again.';
      } else if (error.name === 'InvalidParameterException') {
        errorMessage = 'Invalid request. Please try registering again.';
      }
      
      setErrors({ general: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBackToLogin = () => {
    router.push('/login');
  };

  if (step === 'confirm') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Confirm Your Account</CardTitle>
            <CardDescription>
              We've sent a confirmation code to {formData.email}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleConfirmRegistration} className="space-y-4">
              {errors.general && (
                <Alert variant="destructive">
                  <AlertDescription>{errors.general}</AlertDescription>
                </Alert>
              )}
              
              {errors.success && (
                <Alert>
                  <AlertDescription>{errors.success}</AlertDescription>
                </Alert>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="confirmationCode">Confirmation Code</Label>
                <Input
                  id="confirmationCode"
                  name="confirmationCode"
                  type="text"
                  value={formData.confirmationCode}
                  onChange={handleInputChange}
                  placeholder="Enter 6-digit code"
                  disabled={isSubmitting}
                  className={errors.confirmationCode ? 'border-red-500' : ''}
                  maxLength={6}
                />
                {errors.confirmationCode && (
                  <p className="text-sm text-red-500">{errors.confirmationCode}</p>
                )}
              </div>
              
              <Button
                type="submit"
                className="w-full"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Confirming...
                  </>
                ) : (
                  'Confirm Account'
                )}
              </Button>
              
              <div className="text-center space-y-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleResendCode}
                  disabled={isSubmitting}
                  className="text-sm"
                >
                  Resend Code
                </Button>
                
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setStep('register')}
                  className="text-sm"
                >
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Registration
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">Create Account</CardTitle>
          <CardDescription>
            Sign up for Strands Agent to get started
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRegister} className="space-y-4">
            {errors.general && (
              <Alert variant="destructive">
                <AlertDescription>{errors.general}</AlertDescription>
              </Alert>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                name="username"
                type="text"
                value={formData.username}
                onChange={handleInputChange}
                placeholder="Enter username"
                disabled={isSubmitting}
                className={errors.username ? 'border-red-500' : ''}
              />
              {errors.username && (
                <p className="text-sm text-red-500">{errors.username}</p>
              )}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="Enter your email"
                disabled={isSubmitting}
                className={errors.email ? 'border-red-500' : ''}
              />
              {errors.email && (
                <p className="text-sm text-red-500">{errors.email}</p>
              )}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Enter password"
                  disabled={isSubmitting}
                  className={errors.password ? 'border-red-500 pr-10' : 'pr-10'}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={isSubmitting}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4 text-gray-400" />
                  ) : (
                    <Eye className="h-4 w-4 text-gray-400" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="text-sm text-red-500">{errors.password}</p>
              )}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <div className="relative">
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  placeholder="Confirm password"
                  disabled={isSubmitting}
                  className={errors.confirmPassword ? 'border-red-500 pr-10' : 'pr-10'}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  disabled={isSubmitting}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-4 w-4 text-gray-400" />
                  ) : (
                    <Eye className="h-4 w-4 text-gray-400" />
                  )}
                </button>
              </div>
              {errors.confirmPassword && (
                <p className="text-sm text-red-500">{errors.confirmPassword}</p>
              )}
            </div>
            
            <Button
              type="submit"
              className="w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating Account...
                </>
              ) : (
                'Create Account'
              )}
            </Button>
            
            <div className="text-center">
              <Button
                type="button"
                variant="ghost"
                onClick={handleBackToLogin}
                className="text-sm"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Login
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};