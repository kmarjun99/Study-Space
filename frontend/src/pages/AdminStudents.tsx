import React, { useEffect, useMemo, useState } from 'react';
import { AppState, BookingDurationType, CabinStatus } from '../types';
import { Badge, Button, Card, Input } from '../components/UI';
import { CheckCircle, Clock, FileText, Loader2, Mail, Phone, Plus, Receipt, Search, Send, User as UserIcon, X, XCircle } from 'lucide-react';
import {
  OwnerOperationalAccessStatus,
  OwnerPaymentStatus,
  OwnerStudentAssignmentInput,
  OwnerStudentRow,
  RenewalStatus,
  ownerStudentService,
} from '../services/ownerStudentService';

interface AdminStudentsProps {
  state: AppState;
}

const durationOptions: { value: BookingDurationType; label: string }[] = [
  { value: '1_MONTH', label: '1 Month' },
  { value: '3_MONTHS', label: '3 Months' },
  { value: '6_MONTHS', label: '6 Months' },
  { value: '1_WEEK', label: '1 Week' },
  { value: '1_DAY', label: '1 Day' },
];

const emptyForm = (readingRoomId = ''): OwnerStudentAssignmentInput => ({
  name: '',
  email: '',
  phone: '',
  readingRoomId,
  cabinId: '',
  durationType: '1_MONTH',
  joiningDate: new Date().toISOString().slice(0, 10),
  amount: undefined,
  paymentStatus: 'PENDING',
  paymentReference: '',
  sendInvite: true,
});

const dateLabel = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
};

const renewalBadge = (status?: RenewalStatus) => {
  if (status === 'PAYMENT_PENDING') return { label: 'Payment Pending', variant: 'warning' as const, icon: Clock };
  if (status === 'RENEWAL_DUE') return { label: 'Renewal Due', variant: 'warning' as const, icon: Clock };
  if (status === 'EXPIRED') return { label: 'Expired', variant: 'error' as const, icon: XCircle };
  return { label: 'Active', variant: 'success' as const, icon: CheckCircle };
};

const apiErrorMessage = (err: any, fallback: string) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return fallback;
};

export const AdminStudents: React.FC<AdminStudentsProps> = ({ state }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [renewalFilter, setRenewalFilter] = useState<RenewalStatus | 'ALL'>('ALL');
  const [paymentFilter, setPaymentFilter] = useState<OwnerPaymentStatus | 'ALL'>('ALL');
  const [students, setStudents] = useState<OwnerStudentRow[]>([]);
  const [accessStatuses, setAccessStatuses] = useState<OwnerOperationalAccessStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [resendingStudentId, setResendingStudentId] = useState<string | null>(null);

  const myRooms = useMemo(
    () => state.readingRooms.filter(room => room.ownerId === state.currentUser?.id),
    [state.currentUser?.id, state.readingRooms],
  );
  const defaultRoomId = myRooms[0]?.id || '';
  const [form, setForm] = useState<OwnerStudentAssignmentInput>(() => emptyForm(defaultRoomId));

  useEffect(() => {
    if (defaultRoomId && !form.readingRoomId) {
      setForm(prev => ({ ...prev, readingRoomId: defaultRoomId }));
    }
  }, [defaultRoomId, form.readingRoomId]);

  const cabinsForForm = useMemo(
    () => state.cabins
      .filter(cabin => cabin.readingRoomId === form.readingRoomId)
      .sort((a, b) => Number(a.number) - Number(b.number) || a.number.localeCompare(b.number)),
    [form.readingRoomId, state.cabins],
  );

  const accessByRoom = useMemo(() => {
    const map = new Map<string, OwnerOperationalAccessStatus>();
    accessStatuses.forEach(status => map.set(status.readingRoomId, status));
    return map;
  }, [accessStatuses]);

  const selectedRoomAccess = form.readingRoomId ? accessByRoom.get(form.readingRoomId) : undefined;
  const isSelectedRoomLocked = selectedRoomAccess ? !selectedRoomAccess.canOperate : true;
  const selectedRoomLockMessage = selectedRoomAccess?.message || 'Checking reading room access...';
  const canOpenAddStudent = accessStatuses.some(status => status.canOperate);

  useEffect(() => {
    if (!accessStatuses.length) return;
    const currentAccess = form.readingRoomId ? accessByRoom.get(form.readingRoomId) : undefined;
    if (currentAccess?.canOperate) return;
    const firstOpen = accessStatuses.find(status => status.canOperate);
    if (firstOpen) {
      setForm(prev => ({ ...prev, readingRoomId: firstOpen.readingRoomId, cabinId: '' }));
    }
  }, [accessStatuses, accessByRoom, form.readingRoomId]);

  const loadStudents = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [data, access] = await Promise.all([
        ownerStudentService.list({
          renewalStatus: renewalFilter,
          paymentStatus: paymentFilter,
        }),
        ownerStudentService.accessStatus(),
      ]);
      setStudents(data);
      setAccessStatuses(access);
    } catch (err: any) {
      console.error('Failed to fetch owner students:', err);
      setError(apiErrorMessage(err, 'Failed to load students'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadStudents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renewalFilter, paymentFilter]);

  const filteredStudents = students.filter(student => {
    const needle = searchTerm.trim().toLowerCase();
    if (!needle) return true;
    return (
      student.name.toLowerCase().includes(needle) ||
      student.email.toLowerCase().includes(needle) ||
      (student.phone || '').toLowerCase().includes(needle) ||
      (student.cabinNumber || '').toLowerCase().includes(needle)
    );
  });

  const replaceRow = (updated?: OwnerStudentRow) => {
    if (!updated) return;
    setStudents(prev => {
      const exists = prev.some(row => row.studentId === updated.studentId);
      return exists
        ? prev.map(row => row.studentId === updated.studentId ? updated : row)
        : [updated, ...prev];
    });
  };

  const submitAddStudent = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isSaving) return;
    if (isSelectedRoomLocked) {
      setAddError(selectedRoomLockMessage);
      return;
    }
    try {
      setIsSaving(true);
      setAddError(null);
      setSuccessMessage(null);
      setActionMessage(null);
      setActionError(null);
      const result = await ownerStudentService.create({
        ...form,
        amount: form.amount === undefined || Number.isNaN(Number(form.amount)) ? undefined : Number(form.amount),
      });
      replaceRow(result.student);
      setIsAddOpen(false);
      setForm(emptyForm(defaultRoomId));
      setSuccessMessage(result.message || 'Student assigned successfully.');
    } catch (err: any) {
      console.error('Failed to add student:', err);
      setAddError(apiErrorMessage(err, 'Failed to add student. Please check the form and try again.'));
    } finally {
      setIsSaving(false);
    }
  };

  const renew = async (student: OwnerStudentRow) => {
    if (!student.bookingId) return;
    const access = student.readingRoomId ? accessByRoom.get(student.readingRoomId) : undefined;
    if (access && !access.canOperate) {
      setActionError(access.message);
      return;
    }
    const duration = (window.prompt('Renew for duration (1_MONTH, 3_MONTHS, 6_MONTHS):', student.durationType || '1_MONTH') || '').trim() as BookingDurationType;
    if (!duration) return;
    const amountText = window.prompt('Amount collected for renewal (leave blank to use venue price):', '');
    const paymentStatus = window.confirm('Was payment collected now?') ? 'PAID' : 'PENDING';
    const result = await ownerStudentService.renew(student.bookingId, {
      durationType: duration,
      amount: amountText ? Number(amountText) : undefined,
      paymentStatus,
    });
    replaceRow(result.student);
  };

  const markPaid = async (student: OwnerStudentRow) => {
    if (!student.bookingId) return;
    const access = student.readingRoomId ? accessByRoom.get(student.readingRoomId) : undefined;
    if (access && !access.canOperate) {
      setActionError(access.message);
      return;
    }
    const reference = window.prompt('Payment reference (optional):', '') || undefined;
    const result = await ownerStudentService.markPaid(student.bookingId, undefined, reference);
    replaceRow(result.student);
  };

  const release = async (student: OwnerStudentRow) => {
    if (!student.bookingId) return;
    if (!window.confirm(`Release cabin ${student.cabinNumber || ''} for ${student.name}?`)) return;
    const result = await ownerStudentService.release(student.bookingId);
    replaceRow(result.student);
  };

  const resendInvite = async (student: OwnerStudentRow) => {
    try {
      const access = student.readingRoomId ? accessByRoom.get(student.readingRoomId) : undefined;
      if (access && !access.canOperate) {
        setActionError(access.message);
        return;
      }
      setResendingStudentId(student.studentId);
      setActionError(null);
      setActionMessage(null);
      const result = await ownerStudentService.resendInvite(student.studentId);
      replaceRow(result.student);
      setActionMessage(result.message || `Invite resent to ${student.email}`);
    } catch (err: any) {
      setActionError(apiErrorMessage(err, `Could not resend invite to ${student.email}`));
    } finally {
      setResendingStudentId(null);
    }
  };

  if (!myRooms.length) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center">
        <div className="bg-gray-100 p-4 rounded-full mb-4">
          <UserIcon className="h-8 w-8 text-gray-400" />
        </div>
        <h2 className="text-xl font-bold text-gray-900">No Students Yet</h2>
        <p className="text-gray-500 mt-2">Create a reading room to add and assign students.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Students</h1>
          <p className="text-gray-500">Assign cabins, track renewal windows, and manage offline payments.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full lg:w-auto">
          <div className="relative sm:w-64">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search students..."
              className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-sm"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <Button
            onClick={() => { setAddError(null); setSuccessMessage(null); if (canOpenAddStudent) setIsAddOpen(true); }}
            disabled={!canOpenAddStudent}
            title={!canOpenAddStudent ? 'No reading room is currently eligible for student admission' : undefined}
          >
            <Plus className="w-4 h-4 mr-2" /> Add Student
          </Button>
        </div>
      </div>

      {!canOpenAddStudent && !isLoading && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-semibold">Student admissions are locked</p>
          <p className="mt-1">Your reading room must be verified, live, and have an active plan or admin-granted access before adding students.</p>
          {accessStatuses[0]?.message && <p className="mt-1 text-amber-800">{accessStatuses[0].message}</p>}
        </div>
      )}

      {successMessage && (
        <div className="flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />
          <div>
            <p className="font-semibold">Offline admission saved</p>
            <p>{successMessage}</p>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            className="ml-auto rounded-full p-1 text-green-700 hover:bg-green-100"
            aria-label="Dismiss success message"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {(actionMessage || actionError) && (
        <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${
          actionError
            ? 'border-red-200 bg-red-50 text-red-800'
            : 'border-blue-200 bg-blue-50 text-blue-800'
        }`}>
          {actionError ? <XCircle className="mt-0.5 h-5 w-5 flex-shrink-0" /> : <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />}
          <div>
            <p className="font-semibold">{actionError ? 'Action failed' : 'Invite updated'}</p>
            <p>{actionError || actionMessage}</p>
          </div>
          <button
            type="button"
            onClick={() => { setActionMessage(null); setActionError(null); }}
            className={`ml-auto rounded-full p-1 ${actionError ? 'text-red-700 hover:bg-red-100' : 'text-blue-700 hover:bg-blue-100'}`}
            aria-label="Dismiss action message"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={renewalFilter}
            onChange={(event) => setRenewalFilter(event.target.value as RenewalStatus | 'ALL')}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
          >
            <option value="ALL">All renewal statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="RENEWAL_DUE">Renewal Due</option>
            <option value="EXPIRED">Expired</option>
            <option value="PAYMENT_PENDING">Payment Pending</option>
          </select>
          <select
            value={paymentFilter}
            onChange={(event) => setPaymentFilter(event.target.value as OwnerPaymentStatus | 'ALL')}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
          >
            <option value="ALL">All payment statuses</option>
            <option value="PAID">Paid</option>
            <option value="PENDING">Pending</option>
            <option value="REFUNDED">Refunded</option>
          </select>
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </Card>

      <Card className="overflow-hidden border border-gray-200 shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Student</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Cabin</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Renewal</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Payment</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    <Loader2 className="h-8 w-8 text-indigo-500 animate-spin mx-auto mb-2" />
                    Loading students...
                  </td>
                </tr>
              ) : filteredStudents.length > 0 ? (
                filteredStudents.map(student => {
                  const badge = renewalBadge(student.renewalStatus);
                  const Icon = badge.icon;
                  return (
                    <tr key={student.studentId} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">{student.name}</div>
                        <div className="text-sm text-gray-500 flex items-center gap-1 mt-1">
                          <Mail className="w-3 h-3" /> {student.email}
                        </div>
                        {student.phone && (
                          <div className="text-sm text-gray-500 flex items-center gap-1 mt-1">
                            <Phone className="w-3 h-3" /> {student.phone}
                          </div>
                        )}
                        {student.mustSetPassword && (
                          <Badge variant="warning" className="mt-2">Invite pending</Badge>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-mono font-semibold text-gray-900">{student.cabinNumber || '—'}</div>
                        <div className="text-xs text-gray-500">{student.readingRoomName || 'Reading room'}</div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={badge.variant}>
                          <Icon className="w-3 h-3 mr-1" /> {badge.label}
                        </Badge>
                        <div className="text-xs text-gray-500 mt-2">
                          {dateLabel(student.joiningDate)} → {dateLabel(student.expiryDate)}
                        </div>
                        {student.renewalWindowStart && (
                          <div className="text-xs text-gray-400">
                            Window: {dateLabel(student.renewalWindowStart)} - {dateLabel(student.renewalWindowEnd)}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={student.paymentStatus === 'PAID' ? 'success' : 'warning'}>
                          {student.paymentStatus || '—'}
                        </Badge>
                        <div className="text-sm font-medium text-gray-700 mt-2">₹{student.amount || 0}</div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          {(() => {
                            const rowAccess = student.readingRoomId ? accessByRoom.get(student.readingRoomId) : undefined;
                            const rowLocked = rowAccess ? !rowAccess.canOperate : false;
                            return (
                              <>
                                <Button size="sm" variant="outline" onClick={() => renew(student)} disabled={rowLocked}>Renew</Button>
                                {student.paymentStatus !== 'PAID' && (
                                  <Button size="sm" variant="outline" onClick={() => markPaid(student)} disabled={rowLocked}>Mark Paid</Button>
                                )}
                                {student.mustSetPassword && (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => resendInvite(student)}
                                    isLoading={resendingStudentId === student.studentId}
                                    disabled={rowLocked || resendingStudentId === student.studentId}
                                  >
                                    Resend Invite
                                  </Button>
                                )}
                                <Button size="sm" variant="danger" onClick={() => release(student)}>Release</Button>
                              </>
                            );
                          })()}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">No students found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {isAddOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="add-student-title">
          <div
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
            onClick={() => !isSaving && setIsAddOpen(false)}
          />
          <div className="absolute inset-y-0 right-0 flex w-full max-w-full justify-end">
            <form
              onSubmit={submitAddStudent}
              className="relative flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl"
            >
              <h2 id="add-student-title" className="sr-only">Add offline student</h2>
              <button
                type="button"
                onClick={() => !isSaving && setIsAddOpen(false)}
                disabled={isSaving}
                className="absolute right-4 top-4 z-10 rounded-full border border-gray-200 bg-white p-2 text-gray-400 shadow-sm transition hover:border-gray-300 hover:text-gray-700 disabled:opacity-50"
                aria-label="Close add student drawer"
              >
                <X className="h-5 w-5" />
              </button>

              <div className="flex-1 space-y-5 overflow-y-auto px-6 pb-6 pt-14">
                {addError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <p className="font-semibold">Could not add student</p>
                    <p className="mt-1">{addError}</p>
                  </div>
                )}

                <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
                  <div className="mb-4 flex items-center gap-3">
                    <div className="rounded-xl bg-indigo-50 p-2 text-indigo-600 ring-1 ring-indigo-100">
                      <UserIcon className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-950">Student details</h3>
                      <p className="text-sm text-gray-500">Use the student’s real contact details for invoices and invite delivery.</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Input label="Full name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
                    <Input label="Email address" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
                    <Input label="Phone number" value={form.phone || ''} onChange={e => setForm({ ...form, phone: e.target.value })} />
                    <Input label="Joining date" type="date" value={form.joiningDate} onChange={e => setForm({ ...form, joiningDate: e.target.value })} required />
                  </div>
                </section>

                <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
                  <div className="mb-4 flex items-center gap-3">
                    <div className="rounded-xl bg-purple-50 p-2 text-purple-600 ring-1 ring-purple-100">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-950">Cabin assignment</h3>
                      <p className="text-sm text-gray-500">Choose the reading room, available cabin, and subscription duration.</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">Reading Room</label>
                      <select
                        value={form.readingRoomId}
                        onChange={e => setForm({ ...form, readingRoomId: e.target.value, cabinId: '' })}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        required
                      >
                        {myRooms.map(room => {
                          const access = accessByRoom.get(room.id);
                          return (
                            <option key={room.id} value={room.id} disabled={access ? !access.canOperate : false}>
                              {room.name}{access && !access.canOperate ? ' · Locked' : ''}
                            </option>
                          );
                        })}
                      </select>
                      {selectedRoomAccess && !selectedRoomAccess.canOperate && (
                        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          {selectedRoomAccess.message}
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">Cabin</label>
                      <select
                        value={form.cabinId}
                        onChange={e => setForm({ ...form, cabinId: e.target.value })}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        required
                      >
                        <option value="">Select cabin</option>
                        {cabinsForForm.map(cabin => (
                          <option key={cabin.id} value={cabin.id}>
                            Cabin {cabin.number} · Floor {cabin.floor} · {cabin.status}
                            {cabin.status === CabinStatus.OCCUPIED ? ' (server will validate)' : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">Plan / Duration</label>
                      <select
                        value={form.durationType}
                        onChange={e => setForm({ ...form, durationType: e.target.value as BookingDurationType })}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        {durationOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                      </select>
                    </div>
                  </div>
                </section>

                <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
                  <div className="mb-4 flex items-center gap-3">
                    <div className="rounded-xl bg-green-50 p-2 text-green-600 ring-1 ring-green-100">
                      <Receipt className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-950">Payment and invoice</h3>
                      <p className="text-sm text-gray-500">An invoice is generated automatically. Paid entries are recorded as offline/manual payments.</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <Input
                      label="Amount"
                      type="number"
                      min="0"
                      value={form.amount ?? ''}
                      placeholder="Use venue price"
                      onChange={e => setForm({ ...form, amount: e.target.value ? Number(e.target.value) : undefined })}
                    />
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">Payment status</label>
                      <select
                        value={form.paymentStatus}
                        onChange={e => setForm({ ...form, paymentStatus: e.target.value as OwnerPaymentStatus })}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="PAID">Paid offline</option>
                        <option value="PENDING">Payment pending</option>
                      </select>
                    </div>
                    <Input
                      label="Payment reference"
                      value={form.paymentReference || ''}
                      placeholder="UPI ref / receipt no."
                      onChange={e => setForm({ ...form, paymentReference: e.target.value })}
                    />
                  </div>
                </section>

                <section className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4 sm:p-5">
                  <label className="flex cursor-pointer items-start gap-3">
                    <input
                      type="checkbox"
                      checked={form.sendInvite ?? true}
                      onChange={e => setForm({ ...form, sendInvite: e.target.checked })}
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    <span>
                      <span className="flex items-center gap-2 font-semibold text-gray-950">
                        <Send className="h-4 w-4 text-indigo-600" />
                        Send login invite now
                      </span>
                      <span className="mt-1 block text-sm text-gray-600">
                        The student must verify the invite OTP and set a password before logging in. If you turn this off, the account and invoice are still created and you can resend the invite later.
                      </span>
                    </span>
                  </label>
                </section>
              </div>

              <div className="border-t border-gray-200 bg-white px-6 py-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="max-w-xl text-sm text-gray-500">
                    Student, cabin assignment, booking, invoice, renewal dates, and invite choice are saved together.
                  </p>
                  <div className="flex justify-end gap-3">
                    <Button type="button" variant="ghost" onClick={() => setIsAddOpen(false)} disabled={isSaving}>Cancel</Button>
                    <Button type="submit" isLoading={isSaving} disabled={isSaving || isSelectedRoomLocked} className="min-w-[150px] whitespace-nowrap">
                      {form.sendInvite === false ? 'Add Student' : 'Add & Send Invite'}
                    </Button>
                  </div>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
