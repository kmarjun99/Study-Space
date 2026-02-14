
import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Input, Modal } from '../components/UI';
import { User, UserRole } from '../types';
import { userService } from '../services/userService';

// If UserRole is not exported from types, define it here (or check imports)
// Assuming UserRole is in types based on usage.

interface SuperAdminUsersViewProps {
    users: User[];
}

export const SuperAdminUsersView: React.FC<SuperAdminUsersViewProps> = ({ users }) => {
    const [editingUser, setEditingUser] = useState<any>(null);
    const [isUserModalOpen, setIsUserModalOpen] = useState(false);
    const [localUsers, setLocalUsers] = useState<User[]>(users);

    // Update local users when prop changes
    useEffect(() => {
        setLocalUsers(users);
    }, [users]);

    const handleEditUser = (user: any) => {
        setEditingUser({ ...user });
        setIsUserModalOpen(true);
    };

    const handleSaveUser = async () => {
        if (!editingUser) return;

        try {
            const updated = await userService.updateUser(editingUser.id, {
                name: editingUser.name,
                email: editingUser.email,
                role: editingUser.role,
                verificationStatus: editingUser.verificationStatus
            });

            // Update local users list
            setLocalUsers(prev => prev.map(u => u.id === updated.id ? updated : u));

            setIsUserModalOpen(false);
            setEditingUser(null);
        } catch (error) {
            console.error('Failed to save user:', error);
            alert('Failed to update user. Please try again.');
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">User Directory</h2>
                    <p className="text-gray-500">Manage all students and partners.</p>
                </div>
                <div className="flex gap-2">
                    <Input placeholder="Search users..." className="min-w-[300px]" />
                </div>
            </div>

            <Card className="p-0 overflow-hidden border border-gray-200 shadow-sm">
                <table className="w-full text-left text-sm text-gray-500">
                    <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold">
                        <tr>
                            <th className="px-6 py-4">User Details</th>
                            <th className="px-6 py-4">Role</th>
                            <th className="px-6 py-4">Status</th>
                            <th className="px-6 py-4">Joined</th>
                            <th className="px-6 py-4">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {localUsers.map(user => (
                            <tr key={user.id} className="bg-white hover:bg-gray-50 transition-colors">
                                <td className="px-6 py-4">
                                    <div className="flex items-center">
                                        <div className="h-10 w-10 flex-shrink-0 mr-4">
                                            <img className="h-10 w-10 rounded-full object-cover border border-gray-200" src={user.avatarUrl || `https://ui-avatars.com/api/?name=${user.name}&background=random`} alt="" />
                                        </div>
                                        <div>
                                            <div className="font-medium text-gray-900">{user.name}</div>
                                            <div className="text-gray-500">{user.email}</div>
                                        </div>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <Badge variant={user.role === UserRole.ADMIN ? 'warning' : user.role === UserRole.SUPER_ADMIN ? 'error' : 'success'}>
                                        {user.role}
                                    </Badge>
                                </td>
                                <td className="px-6 py-4">
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                        Active
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-gray-400">
                                    Oct 24, 2023
                                </td>
                                <td className="px-6 py-4">
                                    <Button size="sm" variant="ghost" className="text-indigo-600 hover:text-indigo-900" onClick={() => handleEditUser(user)}>Edit</Button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Card>

            <Modal isOpen={isUserModalOpen} onClose={() => setIsUserModalOpen(false)} title="Edit User">
                <div className="space-y-4">
                    <Input
                        label="Name"
                        value={editingUser?.name || ''}
                        onChange={e => setEditingUser({ ...editingUser, name: e.target.value })}
                    />
                    <Input
                        label="Email"
                        type="email"
                        value={editingUser?.email || ''}
                        onChange={e => setEditingUser({ ...editingUser, email: e.target.value })}
                    />
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                        <select
                            className="w-full border p-2 rounded-lg"
                            value={editingUser?.role || 'STUDENT'}
                            onChange={e => setEditingUser({ ...editingUser, role: e.target.value })}
                        >
                            <option value="STUDENT">Student</option>
                            <option value="ADMIN">Admin</option>
                            <option value="SUPER_ADMIN">Super Admin</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                        <select
                            className="w-full border p-2 rounded-lg"
                            value={editingUser?.status || 'active'}
                            onChange={e => setEditingUser({ ...editingUser, status: e.target.value })}
                        >
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                            <option value="suspended">Suspended</option>
                        </select>
                    </div>
                    <div className="flex justify-end gap-3 mt-6">
                        <Button variant="ghost" onClick={() => setIsUserModalOpen(false)}>Cancel</Button>
                        <Button variant="primary" onClick={handleSaveUser}>Save Changes</Button>
                    </div>
                </div>
            </Modal>
        </div>
    );
};
