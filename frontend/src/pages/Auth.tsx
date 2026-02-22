
import React, { useState, useEffect } from 'react';

import { UserRole } from '../types';
import { Button, Input, Card } from '../components/UI';
import { Logo } from '../components/Logo';

import { BookOpen, Mail, Lock, User as UserIcon, Eye, EyeOff, CheckCircle, XCircle, Shield } from 'lucide-react';
import { authService } from '../services/authService';
import { validateEmail, validatePassword } from '../utils/security';

interface AuthProps {
  onLogin: (email: string, role: UserRole, user?: any) => void;
}

export const AuthPage: React.FC<AuthProps> = ({ onLogin }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const [role, setRole] = useState<UserRole>(UserRole.STUDENT);
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  // Email validation states
  const [emailError, setEmailError] = useState<string>('');
  const [emailTouched, setEmailTouched] = useState(false);
  const [isEmailValid, setIsEmailValid] = useState(false);

  // Password validation states
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [showPasswordStrength, setShowPasswordStrength] = useState(false);

  // OTP verification states
  const [showOtpModal, setShowOtpModal] = useState(false);
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [otpError, setOtpError] = useState<string>('');
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [resendTimer, setResendTimer] = useState(0);
  const [otpType, setOtpType] = useState<string>('registration'); // 'registration' or 'password_reset'

  // Forgot password states
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [forgotPasswordEmail, setForgotPasswordEmail] = useState('');
  const [resetNewPassword, setResetNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [showResetPassword, setShowResetPassword] = useState(false);

  // Auto-fill removed to allow manual demo credential selection
  // useEffect(() => {
  //   if (role === UserRole.ADMIN) {
  //     setEmail('admin@studyspace.com');
  //     setPassword('admin123');
  //   } else {
  //     setEmail('student1@studyspace.com');
  //     setPassword('student123');
  //   }
  // }, [role]);

  // Real-time email validation
  useEffect(() => {
    if (email && emailTouched) {
      if (!validateEmail(email)) {
        setEmailError('Please enter a valid email address');
        setIsEmailValid(false);
      } else {
        setEmailError('');
        setIsEmailValid(true);
      }
    }
  }, [email, emailTouched]);

  // Real-time password validation
  useEffect(() => {
    if (password && passwordTouched && isRegister) {
      const validation = validatePassword(password);
      setPasswordErrors(validation.errors);
    }
  }, [password, passwordTouched, isRegister]);

  // OTP resend timer
  useEffect(() => {
    if (resendTimer > 0) {
      const timer = setTimeout(() => setResendTimer(resendTimer - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendTimer]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate email format
    if (!validateEmail(email)) {
      setEmailError('Please enter a valid email address');
      setEmailTouched(true);
      return;
    }

    // Validate password strength for registration
    if (isRegister) {
      const validation = validatePassword(password);
      if (!validation.isValid) {
        setPasswordErrors(validation.errors);
        setPasswordTouched(true);
        setError('Please fix password errors before continuing');
        return;
      }
    }

    setIsLoading(true);

    try {
      let data;
      if (isRegister) {
        // Register now sends OTP automatically and returns OTP response
        await authService.register(email, password, role, name);

        // Show OTP verification modal
        setShowOtpModal(true);
        setOtpType('registration');
        setOtpSent(true);
        setResendTimer(60);
        setIsLoading(false);
        return;
      } else {
        data = await authService.login(email, password);
      }

      if (data && data.access_token) {
        localStorage.setItem('studySpace_token', data.access_token);

        // Use the user data returned efficiently from the login response
        const user = {
          id: data.user_id,
          name: data.name,
          email: data.email,
          role: data.role,
          avatarUrl: data.avatar_url,
          // phone: data.phone, // If we added phone to token response
          has_active_waitlist: data.has_active_waitlist
        };

        let userRoleToPass = user.role as UserRole;
        if (user.email === 'superadmin@studyspace.com') {
          userRoleToPass = UserRole.SUPER_ADMIN;
        }
        onLogin(user.email, userRoleToPass, user);
      }

    } catch (err: any) {
      console.error('Authentication failed:', err);
      const detail = err.response?.data?.detail;

      // Log full error for debugging
      // console.log('Error response:', err.response?.data);

      if (detail) {
        // Handle specific registration errors
        if (typeof detail === 'string') {
          if (detail.includes('already exists')) {
            setError('This email is already registered. Please login or use a different email.');
          } else {
            setError(detail);
          }
        } else {
          setError(JSON.stringify(detail));
        }
      } else if (!err.response) {
        setError('Cannot connect to server. Ensure you are using the correct local IP.');
      } else {
        setError(isRegister
          ? 'Registration failed. Please check your details.'
          : 'Incorrect email or password. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) return;

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    setOtpError('');

    // Auto-focus next input
    if (value && index < 5) {
      const nextInput = document.getElementById(`otp-${index + 1}`);
      nextInput?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const prevInput = document.getElementById(`otp-${index - 1}`);
      prevInput?.focus();
    }
  };

  const handleVerifyOtp = async () => {
    const otpCode = otp.join('');

    if (otpCode.length !== 6) {
      setOtpError('Please enter complete 6-digit OTP');
      return;
    }

    setIsVerifyingOtp(true);
    setOtpError('');

    try {
      if (otpType === 'password_reset') {
        // Verify OTP for password reset
        await authService.verifyOtp(forgotPasswordEmail, otpCode, 'password_reset');
        setShowOtpModal(false);
        setShowResetPassword(true);
      } else {
        // Complete registration: verify OTP and create user
        const data = await authService.completeRegistration(email, otpCode, password, name, role);
        if (data && data.access_token) {
          localStorage.setItem('studySpace_token', data.access_token);

          const user = {
            id: data.user_id,
            name: data.name,
            email: data.email,
            role: data.role,
            avatarUrl: data.avatar_url,
            has_active_waitlist: data.has_active_waitlist
          };

          let userRoleToPass = user.role as UserRole;
          if (user.email === 'superadmin@studyspace.com') {
            userRoleToPass = UserRole.SUPER_ADMIN;
          }
          setShowOtpModal(false);
          onLogin(user.email, userRoleToPass, user);
        }
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Verification failed. Please try again.';
      setOtpError(errorMsg);
    } finally {
      setIsVerifyingOtp(false);
    }
  };

  const handleResendOtp = async () => {
    setResendTimer(60);
    setOtp(['', '', '', '', '', '']);
    setOtpError('');

    try {
      const emailToUse = otpType === 'password_reset' ? forgotPasswordEmail : email;

      await authService.resendOtp(emailToUse, null, otpType);
      setOtpSent(true);
    } catch (err: any) {
      setOtpError('Failed to resend OTP. Please try again.');
    }
  };

  const handleForgotPassword = async () => {
    if (!forgotPasswordEmail || !validateEmail(forgotPasswordEmail)) {
      setError('Please enter a valid email address');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await authService.forgotPassword(forgotPasswordEmail);
      setShowForgotPassword(false);
      setShowOtpModal(true);
      setOtpType('password_reset');
      setOtpSent(true);
      setResendTimer(60);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to send reset code. Please try again.';
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (resetNewPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (resetNewPassword !== confirmNewPassword) {
      setError('Passwords do not match');
      return;
    }

    const validation = validatePassword(resetNewPassword);
    if (!validation.isValid) {
      setError(validation.errors.join('. '));
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const otpCode = otp.join('');
      await authService.resetPassword(forgotPasswordEmail, otpCode, resetNewPassword);

      setShowResetPassword(false);
      setOtp(['', '', '', '', '', '']);
      setForgotPasswordEmail('');
      setResetNewPassword('');
      setConfirmNewPassword('');
      setError(null);

      // Show success message
      alert('Password reset successful! You can now log in with your new password.');

      // Pre-fill email for login
      setEmail(forgotPasswordEmail);
      setPassword('');
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to reset password. Please try again.';
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 flex items-center justify-center p-4">
      {/* Animated Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-gradient-to-br from-indigo-200/30 to-purple-200/30 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-gradient-to-br from-pink-200/30 to-purple-200/30 rounded-full blur-3xl animate-pulse delay-700"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-br from-blue-100/20 to-indigo-100/20 rounded-full blur-3xl"></div>
      </div>

      <div className="relative z-10 w-full max-w-[440px] max-h-[90vh] overflow-y-auto">
        <div className="w-full bg-white/95 backdrop-blur-xl rounded-3xl shadow-[0_20px_60px_rgba(99,102,241,0.15)] p-8 sm:p-10 border border-white/60 animate-in fade-in slide-in-from-bottom-4 duration-700">
          {/* Decorative Top Border */}
          <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-24 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-full"></div>

          <div className="text-center mb-8">
            <div className="inline-block animate-in zoom-in duration-500">
              <Logo variant="auth" />
            </div>

            <h2 className="text-3xl font-bold text-gray-900 mt-4 tracking-tight animate-in slide-in-from-top-2 fade-in duration-500 delay-100">
              {isRegister ? 'Create account' : 'Welcome back'}
            </h2>
            <p className="mt-2 text-sm text-gray-600 font-medium animate-in slide-in-from-top-2 fade-in duration-500 delay-200">
              {isRegister ? 'Book spaces or list yours' : 'Manage your bookings or venue'}
            </p>
          </div>

          {isRegister && (
            <div className="flex flex-col space-y-2 mb-6 animate-in slide-in-from-top-2 fade-in duration-500 delay-300">
              <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1 ml-1">Sign up as</label>
              <div className="flex justify-center bg-gradient-to-r from-gray-50 to-gray-100/50 p-1.5 rounded-2xl shadow-inner border border-gray-200/50">
                <button
                  type="button"
                  onClick={() => setRole(UserRole.STUDENT)}
                  className={`flex-1 py-2.5 text-sm font-bold rounded-xl transition-all duration-300 ${role === UserRole.STUDENT
                    ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 text-white shadow-lg shadow-indigo-500/30 scale-[1.02]'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-white/50'
                    }`}
                >
                  👤 User
                </button>
                <button
                  type="button"
                  onClick={() => setRole(UserRole.ADMIN)}
                  className={`flex-1 py-2.5 text-sm font-bold rounded-xl transition-all duration-300 ${role === UserRole.ADMIN
                    ? 'bg-gradient-to-br from-purple-500 to-purple-600 text-white shadow-lg shadow-purple-500/30 scale-[1.02]'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-white/50'
                    }`}
                >
                  🏢 Owner
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-gradient-to-r from-red-50 to-pink-50 border-l-4 border-red-500 text-red-700 p-4 rounded-xl text-sm text-left mb-4 shadow-sm animate-in slide-in-from-top-2 fade-in duration-300">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center mt-0.5">
                  <span className="text-white text-xs font-bold">!</span>
                </div>
                <span className="flex-1">{error}</span>
              </div>
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            {isRegister && (
              <>
                <div className="relative group animate-in slide-in-from-left fade-in duration-500 delay-400">
                  <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5 ml-1 block">Full Name</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <UserIcon className="h-5 w-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                    </div>
                    <Input
                      placeholder="John Doe"
                      className="pl-11 h-12 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 border-gray-200 focus:bg-white focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 placeholder:text-gray-400 transition-all duration-300 hover:border-gray-300"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required={isRegister}
                    />
                  </div>
                </div>
              </>
            )}

            <div className={`relative group ${isRegister ? 'animate-in slide-in-from-left fade-in duration-500 delay-450' : 'animate-in slide-in-from-left fade-in duration-500 delay-300'}`}>
              <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5 ml-1 block">Email Address</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                </div>
                <div className="absolute inset-y-0 right-0 pr-4 flex items-center">
                  {emailTouched && email && (
                    isEmailValid ? (
                      <CheckCircle className="h-5 w-5 text-green-500 animate-in zoom-in duration-300" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500 animate-in zoom-in duration-300" />
                    )
                  )}
                </div>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  className={`pl-11 pr-11 h-12 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 border-gray-200 focus:bg-white focus:ring-2 placeholder:text-gray-400 transition-all duration-300 hover:border-gray-300 ${emailTouched && emailError
                    ? 'border-red-300 focus:border-red-400 focus:ring-red-500/30'
                    : emailTouched && isEmailValid
                      ? 'border-green-300 focus:border-green-400 focus:ring-green-500/30'
                      : 'focus:ring-indigo-500/30 focus:border-indigo-400'
                    }`}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={() => setEmailTouched(true)}
                  required
                />
              </div>
              {emailTouched && emailError && (
                <p className="text-xs text-red-600 mt-1.5 ml-1 flex items-center gap-1 animate-in slide-in-from-top-1 fade-in duration-200">
                  <XCircle className="h-3 w-3" />
                  {emailError}
                </p>
              )}
              {emailTouched && isEmailValid && (
                <p className="text-xs text-green-600 mt-1.5 ml-1 flex items-center gap-1 animate-in slide-in-from-top-1 fade-in duration-200">
                  <CheckCircle className="h-3 w-3" />
                  Valid email address
                </p>
              )}
            </div>

            <div className={`relative group ${isRegister ? 'animate-in slide-in-from-left fade-in duration-500 delay-600' : 'animate-in slide-in-from-left fade-in duration-500 delay-400'}`}>
              <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5 ml-1 block">Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                </div>
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  className={`pl-11 pr-11 h-12 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 border-gray-200 focus:bg-white focus:ring-2 placeholder:text-gray-400 transition-all duration-300 hover:border-gray-300 ${passwordTouched && passwordErrors.length > 0 && isRegister
                    ? 'border-red-300 focus:border-red-400 focus:ring-red-500/30'
                    : 'focus:ring-indigo-500/30 focus:border-indigo-400'
                    }`}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => isRegister && setShowPasswordStrength(true)}
                  onBlur={() => {
                    setPasswordTouched(true);
                    setShowPasswordStrength(false);
                  }}
                  required
                />

                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-indigo-600 focus:outline-none transition-colors"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>

              {/* Password Strength Indicator */}
              {isRegister && (showPasswordStrength || passwordTouched) && (
                <div className="mt-3 p-3 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl border border-indigo-100 animate-in slide-in-from-top-2 fade-in duration-300">
                  <p className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <Shield className="h-3.5 w-3.5 text-indigo-600" />
                    Password Requirements
                  </p>
                  <ul className="space-y-1.5">
                    {[
                      { test: password.length >= 8, text: 'At least 8 characters' },
                      { test: /[A-Z]/.test(password), text: 'One uppercase letter' },
                      { test: /[a-z]/.test(password), text: 'One lowercase letter' },
                      { test: /\d/.test(password), text: 'One number' },
                      { test: /[!@#$%^&*(),.?":{}|<>]/.test(password), text: 'One special character' },
                    ].map((req, idx) => (
                      <li key={idx} className="flex items-center gap-2 text-xs">
                        {req.test ? (
                          <CheckCircle className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                        ) : (
                          <div className="h-3.5 w-3.5 rounded-full border-2 border-gray-300 flex-shrink-0" />
                        )}
                        <span className={req.test ? 'text-green-700 font-medium' : 'text-gray-600'}>
                          {req.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            {isRegister && passwordTouched && passwordErrors.length > 0 && (
              <div className="text-xs text-red-600 space-y-1 animate-in slide-in-from-top-1 fade-in duration-200">
                {passwordErrors.map((err, idx) => (
                  <p key={idx} className="flex items-center gap-1">
                    <XCircle className="h-3 w-3" />
                    {err}
                  </p>
                ))}
              </div>
            )}

            {!isRegister && (
              <div className="flex justify-end pt-1 animate-in fade-in duration-500 delay-500">
                <button
                  type="button"
                  onClick={() => setShowForgotPassword(true)}
                  className="text-sm text-indigo-600 hover:text-indigo-700 font-semibold transition-colors hover:underline"
                >
                  Forgot password?
                </button>
              </div>
            )}


            <Button
              type="submit"
              className={`w-full h-13 rounded-xl font-bold text-base shadow-lg bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 hover:from-indigo-700 hover:via-purple-700 hover:to-indigo-700 active:scale-[0.98] transition-all duration-300 mt-6 ${isRegister ? 'animate-in slide-in-from-bottom fade-in duration-500 delay-700' : 'animate-in slide-in-from-bottom fade-in duration-500 delay-600'} bg-[length:200%_100%] hover:bg-[position:100%_0] animate-gradient`}
              size="lg"
              isLoading={isLoading}
            >
              {isRegister
                ? (role === UserRole.ADMIN ? '🏢 Create Owner Account' : '🎓 Create Account')
                : '🚀 Log In'}
            </Button>
          </form>

          {isRegister && (
            <div className="text-center text-xs text-gray-500 mt-6 leading-relaxed animate-in fade-in duration-500 delay-800">
              By creating an account, you agree to StudySpace's <br />
              <span className="text-indigo-600 cursor-pointer hover:text-indigo-700 hover:underline font-semibold">Terms of Service</span> and <span className="text-indigo-600 cursor-pointer hover:text-indigo-700 hover:underline font-semibold">Privacy Policy</span>
            </div>
          )}

          <div className={`text-center text-sm pt-6 border-t border-gray-200 mt-6 ${isRegister ? 'animate-in fade-in duration-500 delay-900' : 'animate-in fade-in duration-500 delay-700'}`}>
            <span className="text-gray-600">
              {isRegister ? 'Already have an account?' : "Don't have an account?"}
            </span>
            <button
              onClick={() => setIsRegister(!isRegister)}
              className="ml-2 font-bold text-indigo-600 hover:text-indigo-700 hover:underline transition-colors"
            >
              {isRegister ? 'Log in' : 'Sign up'}
            </button>
          </div>


          <div className={`text-center text-xs text-gray-400 mt-6 space-y-2 ${isRegister ? 'animate-in fade-in duration-500 delay-1000' : 'animate-in fade-in duration-500 delay-800'}`}>
            {/* Demo credentials removed for production */}
          </div>
        </div>

        {/* OTP Verification Modal */}
        {showOtpModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-300">
            <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8 animate-in zoom-in slide-in-from-bottom-4 duration-500">
              {/* Header */}
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 animate-pulse">
                  <Shield className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-2">Verify Your Identity</h3>
                <p className="text-sm text-gray-600">
                  We've sent a 6-digit code to<br />
                  <span className="font-semibold text-indigo-600 flex items-center justify-center gap-2 mt-1">
                    <Mail className="w-4 h-4" />
                    {otpType === 'password_reset' ? forgotPasswordEmail : email}
                  </span>
                </p>
              </div>

              {/* OTP Input */}
              <div className="mb-6">
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3 text-center">
                  Enter OTP Code
                </label>
                <div className="flex gap-2 justify-center mb-4">
                  {otp.map((digit, index) => (
                    <input
                      key={index}
                      id={`otp-${index}`}
                      type="text"
                      maxLength={1}
                      value={digit}
                      onChange={(e) => handleOtpChange(index, e.target.value)}
                      onKeyDown={(e) => handleOtpKeyDown(index, e)}
                      className="w-12 h-14 text-center text-2xl font-bold border-2 border-gray-300 rounded-xl focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 outline-none transition-all bg-gradient-to-br from-gray-50 to-gray-100/50 focus:bg-white"
                      autoComplete="off"
                    />
                  ))}
                </div>

                {otpError && (
                  <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-3 rounded-lg text-sm mb-4 animate-in slide-in-from-top-2 fade-in duration-300">
                    <div className="flex items-center gap-2">
                      <XCircle className="h-4 w-4" />
                      <span>{otpError}</span>
                    </div>
                  </div>
                )}

                {/* Development Mode Info - Only show if email not configured */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-3 mb-4">
                  <p className="text-xs text-blue-800 font-medium text-center">
                    📧 Check your email for the 6-digit verification code
                  </p>
                  <p className="text-xs text-blue-600 mt-1 text-center">
                    Didn't receive it? Click "Resend OTP" below
                  </p>
                </div>
              </div>

              {/* Verify Button */}
              <Button
                onClick={handleVerifyOtp}
                className="w-full h-12 rounded-xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg"
                isLoading={isVerifyingOtp}
              >
                Verify & Continue
              </Button>

              {/* Resend OTP */}
              <div className="text-center mt-4">
                {resendTimer > 0 ? (
                  <p className="text-sm text-gray-500">
                    Resend OTP in <span className="font-bold text-indigo-600">{resendTimer}s</span>
                  </p>
                ) : (
                  <button
                    onClick={handleResendOtp}
                    className="text-sm text-indigo-600 hover:text-indigo-700 font-semibold hover:underline"
                  >
                    Resend OTP
                  </button>
                )}
              </div>

              {/* Cancel */}
              <button
                onClick={() => {
                  setShowOtpModal(false);
                  setOtp(['', '', '', '', '', '']);
                  setOtpError('');
                }}
                className="w-full mt-4 text-sm text-gray-500 hover:text-gray-700 font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Forgot Password Modal */}
        {showForgotPassword && !showOtpModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-300 p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8 animate-in zoom-in duration-300">
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-full mb-4">
                  <Mail className="h-8 w-8 text-indigo-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Reset Password</h2>
                <p className="text-sm text-gray-600">
                  Enter your email address and we'll send you an OTP to reset your password
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5 ml-1 block">
                    Email Address
                  </label>
                  <Input
                    type="email"
                    placeholder="you@example.com"
                    value={forgotPasswordEmail}
                    onChange={(e) => setForgotPasswordEmail(e.target.value)}
                    className="h-12 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 border-gray-200 focus:bg-white focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400"
                  />
                </div>

                <Button
                  onClick={handleForgotPassword}
                  className="w-full h-12 rounded-xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg"
                  disabled={!forgotPasswordEmail || !validateEmail(forgotPasswordEmail)}
                >
                  Send OTP
                </Button>

                <button
                  onClick={() => {
                    setShowForgotPassword(false);
                    setForgotPasswordEmail('');
                  }}
                  className="w-full text-sm text-gray-500 hover:text-gray-700 font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Password Reset Form */}
        {showResetPassword && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-300 p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8 animate-in zoom-in duration-300">
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-green-100 to-emerald-100 rounded-full mb-4">
                  <Lock className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Create New Password</h2>
                <p className="text-sm text-gray-600">
                  Enter your new password below
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5 ml-1 block">
                    New Password
                  </label>
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      placeholder="••••••••"
                      value={resetNewPassword}
                      onChange={(e) => setResetNewPassword(e.target.value)}
                      className="h-12 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 border-gray-200 focus:bg-white focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 pr-11"
                    />
                    <button
                      type="button"
                      className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-indigo-600 focus:outline-none transition-colors"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5 ml-1 block">
                    Confirm New Password
                  </label>
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    className="h-12 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 border-gray-200 focus:bg-white focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400"
                  />
                  {confirmNewPassword && resetNewPassword !== confirmNewPassword && (
                    <p className="text-xs text-red-600 mt-1.5 ml-1 flex items-center gap-1">
                      <XCircle className="h-3 w-3" />
                      Passwords do not match
                    </p>
                  )}
                  {confirmNewPassword && resetNewPassword === confirmNewPassword && (
                    <p className="text-xs text-green-600 mt-1.5 ml-1 flex items-center gap-1">
                      <CheckCircle className="h-3 w-3" />
                      Passwords match
                    </p>
                  )}
                </div>

                {/* Password Requirements */}
                {resetNewPassword && (
                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-3">
                    <p className="text-xs font-semibold text-gray-700 mb-2">
                      Password Requirements
                    </p>
                    <ul className="space-y-1.5">
                      {[
                        { test: resetNewPassword.length >= 8, text: 'At least 8 characters' },
                        { test: /[A-Z]/.test(resetNewPassword), text: 'One uppercase letter' },
                        { test: /[a-z]/.test(resetNewPassword), text: 'One lowercase letter' },
                        { test: /\d/.test(resetNewPassword), text: 'One number' },
                        { test: /[!@#$%^&*(),.?":{}|<>]/.test(resetNewPassword), text: 'One special character' },
                      ].map((req, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs">
                          {req.test ? (
                            <CheckCircle className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                          ) : (
                            <div className="h-3.5 w-3.5 rounded-full border-2 border-gray-300 flex-shrink-0" />
                          )}
                          <span className={req.test ? 'text-green-700' : 'text-gray-600'}>{req.text}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {error && (
                  <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-3 rounded-lg text-sm">
                    <div className="flex items-center gap-2">
                      <XCircle className="h-4 w-4" />
                      <span>{error}</span>
                    </div>
                  </div>
                )}

                <Button
                  onClick={handleResetPassword}
                  className="w-full h-12 rounded-xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 shadow-lg"
                  disabled={!resetNewPassword || !confirmNewPassword || resetNewPassword !== confirmNewPassword || !validatePassword(resetNewPassword).isValid}
                  isLoading={isLoading}
                >
                  Reset Password
                </Button>

                <button
                  onClick={() => {
                    setShowResetPassword(false);
                    setResetNewPassword('');
                    setConfirmNewPassword('');
                    setError(null);
                  }}
                  className="w-full text-sm text-gray-500 hover:text-gray-700 font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};