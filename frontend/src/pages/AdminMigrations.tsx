import React, { useState } from 'react';
import { Button, Card } from '../components/UI';
import { CheckCircle, AlertTriangle, Loader, Database, Home } from 'lucide-react';
import api from '../services/api';
import toast from 'react-hot-toast';

export const AdminMigrations: React.FC = () => {
    const [isRunning, setIsRunning] = useState(false);
    const [logs, setLogs] = useState<string[]>([]);
    const [success, setSuccess] = useState<boolean | null>(null);

    const runHouseMigration = async () => {
        setIsRunning(true);
        setLogs([]);
        setSuccess(null);

        try {
            const response = await api.post('/admin/migration/add-house-type');
            
            setSuccess(response.data.success);
            setLogs(response.data.logs || []);
            
            if (response.data.success) {
                toast.success('✅ HOUSE type added successfully!');
            } else {
                toast.error('Migration failed. Check logs below.');
            }
        } catch (error: any) {
            setSuccess(false);
            setLogs([`Error: ${error.response?.data?.detail || error.message}`]);
            toast.error('Failed to run migration');
        } finally {
            setIsRunning(false);
        }
    };

    const runFullEnumMigration = async () => {
        setIsRunning(true);
        setLogs([]);
        setSuccess(null);

        try {
            const response = await api.post('/admin/migration/run-enum-migration');
            
            setSuccess(response.data.success);
            setLogs(response.data.logs || []);
            
            if (response.data.success) {
                toast.success('✅ Full migration completed!');
            } else {
                toast.error('Migration failed. Check logs below.');
            }
        } catch (error: any) {
            setSuccess(false);
            setLogs([`Error: ${error.response?.data?.detail || error.message}`]);
            toast.error('Failed to run migration');
        } finally {
            setIsRunning(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-4xl mx-auto">
                <div className="mb-6">
                    <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
                        <Database className="w-8 h-8 text-indigo-600" />
                        Database Migrations
                    </h1>
                    <p className="text-gray-600 mt-2">
                        Run database migrations to add new features
                    </p>
                </div>

                {/* Migration Cards */}
                <div className="space-y-6">
                    
                    {/* Add HOUSE Type Migration */}
                    <Card className="p-6">
                        <div className="flex items-start gap-4">
                            <div className="p-3 bg-indigo-50 rounded-lg">
                                <Home className="w-6 h-6 text-indigo-600" />
                            </div>
                            <div className="flex-1">
                                <h3 className="text-lg font-bold text-gray-900 mb-2">
                                    Add HOUSE Accommodation Type
                                </h3>
                                <p className="text-sm text-gray-600 mb-4">
                                    This migration adds "HOUSE" as a new accommodation type alongside PG and HOSTEL.
                                    Run this if you're getting an error when trying to create a HOUSE accommodation.
                                </p>
                                <div className="flex items-center gap-3">
                                    <Button
                                        onClick={runHouseMigration}
                                        disabled={isRunning}
                                        className="bg-indigo-600 hover:bg-indigo-700"
                                    >
                                        {isRunning ? (
                                            <>
                                                <Loader className="w-4 h-4 mr-2 animate-spin" />
                                                Running...
                                            </>
                                        ) : (
                                            <>
                                                <Home className="w-4 h-4 mr-2" />
                                                Add HOUSE Type
                                            </>
                                        )}
                                    </Button>
                                    <span className="text-xs text-gray-500">
                                        Quick migration (~5 seconds)
                                    </span>
                                </div>
                            </div>
                        </div>
                    </Card>

                    {/* Full Enum Migration */}
                    <Card className="p-6 border-amber-200">
                        <div className="flex items-start gap-4">
                            <div className="p-3 bg-amber-50 rounded-lg">
                                <Database className="w-6 h-6 text-amber-600" />
                            </div>
                            <div className="flex-1">
                                <h3 className="text-lg font-bold text-gray-900 mb-2 flex items-center gap-2">
                                    Full Enum to VARCHAR Migration
                                    <span className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded">Advanced</span>
                                </h3>
                                <p className="text-sm text-gray-600 mb-4">
                                    Converts PostgreSQL enums to VARCHAR columns for more flexibility.
                                    Only run this if the "Add HOUSE Type" migration fails.
                                </p>
                                <div className="flex items-center gap-3">
                                    <Button
                                        onClick={runFullEnumMigration}
                                        disabled={isRunning}
                                        variant="secondary"
                                    >
                                        {isRunning ? (
                                            <>
                                                <Loader className="w-4 h-4 mr-2 animate-spin" />
                                                Running...
                                            </>
                                        ) : (
                                            <>
                                                <Database className="w-4 h-4 mr-2" />
                                                Run Full Migration
                                            </>
                                        )}
                                    </Button>
                                    <span className="text-xs text-gray-500">
                                        May take 30-60 seconds
                                    </span>
                                </div>
                            </div>
                        </div>
                    </Card>

                    {/* Status Card */}
                    {(success !== null || logs.length > 0) && (
                        <Card className={`p-6 ${success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                            <div className="flex items-start gap-3 mb-4">
                                {success ? (
                                    <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0 mt-1" />
                                ) : (
                                    <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0 mt-1" />
                                )}
                                <div className="flex-1">
                                    <h4 className={`font-bold text-lg ${success ? 'text-green-900' : 'text-red-900'}`}>
                                        {success ? 'Migration Successful! ✅' : 'Migration Failed ❌'}
                                    </h4>
                                    {success && (
                                        <p className="text-green-700 text-sm mt-1">
                                            You can now create HOUSE accommodations!
                                        </p>
                                    )}
                                </div>
                            </div>

                            {/* Logs */}
                            {logs.length > 0 && (
                                <div className="mt-4">
                                    <h5 className="text-sm font-semibold text-gray-700 mb-2">Migration Logs:</h5>
                                    <div className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto max-h-96 text-xs font-mono">
                                        {logs.map((log, index) => (
                                            <div key={index} className="mb-1">
                                                {log}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </Card>
                    )}

                    {/* Info Card */}
                    <Card className="p-6 bg-blue-50 border-blue-200">
                        <div className="flex items-start gap-3">
                            <AlertTriangle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                            <div className="text-sm text-blue-800">
                                <p className="font-semibold mb-2">Important Notes:</p>
                                <ul className="list-disc list-inside space-y-1 text-blue-700">
                                    <li>Only admins can run migrations</li>
                                    <li>Migrations are safe to run multiple times</li>
                                    <li>Start with "Add HOUSE Type" - it's faster</li>
                                    <li>Use "Full Migration" only if HOUSE migration fails</li>
                                    <li>Existing data will not be affected</li>
                                </ul>
                            </div>
                        </div>
                    </Card>
                </div>
            </div>
        </div>
    );
};
