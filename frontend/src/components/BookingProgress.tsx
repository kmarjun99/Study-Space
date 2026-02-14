import React from 'react';
import { Check, Eye, Grid3X3, FileText, CreditCard } from 'lucide-react';

interface BookingProgressProps {
    currentStep: 1 | 2 | 3 | 4;
    className?: string;
}

const STEPS = [
    { id: 1, label: 'Explore', icon: Eye, description: 'View venue' },
    { id: 2, label: 'Select', icon: Grid3X3, description: 'Choose seat' },
    { id: 3, label: 'Review', icon: FileText, description: 'Confirm plan' },
    { id: 4, label: 'Subscribe', icon: CreditCard, description: 'Complete' }
];

export const BookingProgress: React.FC<BookingProgressProps> = ({
    currentStep,
    className = ''
}) => {
    return (
        <div className={`w-full ${className}`}>
            {/* Desktop View */}
            <div className="hidden md:flex items-center justify-between">
                {STEPS.map((step, index) => {
                    const isCompleted = step.id < currentStep;
                    const isCurrent = step.id === currentStep;
                    const isUpcoming = step.id > currentStep;
                    const Icon = step.icon;

                    return (
                        <React.Fragment key={step.id}>
                            {/* Step Circle + Label */}
                            <div className="flex flex-col items-center">
                                <div
                                    className={`
                    flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all duration-300
                    ${isCompleted ? 'bg-green-500 border-green-500 text-white' : ''}
                    ${isCurrent ? 'bg-indigo-600 border-indigo-600 text-white scale-110 shadow-lg shadow-indigo-200' : ''}
                    ${isUpcoming ? 'bg-gray-100 border-gray-300 text-gray-400' : ''}
                  `}
                                >
                                    {isCompleted ? (
                                        <Check className="w-5 h-5" />
                                    ) : (
                                        <Icon className="w-5 h-5" />
                                    )}
                                </div>
                                <span className={`mt-2 text-xs font-semibold ${isCurrent ? 'text-indigo-600' : isCompleted ? 'text-green-600' : 'text-gray-400'}`}>
                                    {step.label}
                                </span>
                                <span className={`text-[10px] ${isCurrent ? 'text-gray-600' : 'text-gray-400'}`}>
                                    {step.description}
                                </span>
                            </div>

                            {/* Connector Line */}
                            {index < STEPS.length - 1 && (
                                <div className="flex-1 mx-4">
                                    <div
                                        className={`h-1 rounded-full transition-all duration-300 ${step.id < currentStep ? 'bg-green-500' : 'bg-gray-200'
                                            }`}
                                    />
                                </div>
                            )}
                        </React.Fragment>
                    );
                })}
            </div>

            {/* Mobile View - Compact */}
            <div className="md:hidden">
                <div className="flex items-center justify-between bg-gray-50 rounded-xl p-2">
                    {STEPS.map((step) => {
                        const isCompleted = step.id < currentStep;
                        const isCurrent = step.id === currentStep;
                        const Icon = step.icon;

                        return (
                            <div
                                key={step.id}
                                className={`
                  flex items-center justify-center w-10 h-10 rounded-full transition-all
                  ${isCompleted ? 'bg-green-500 text-white' : ''}
                  ${isCurrent ? 'bg-indigo-600 text-white scale-110 shadow-md' : ''}
                  ${!isCompleted && !isCurrent ? 'bg-gray-200 text-gray-400' : ''}
                `}
                            >
                                {isCompleted ? (
                                    <Check className="w-4 h-4" />
                                ) : (
                                    <Icon className="w-4 h-4" />
                                )}
                            </div>
                        );
                    })}
                </div>
                {/* Current Step Label */}
                <p className="text-center text-xs font-medium text-indigo-600 mt-2">
                    Step {currentStep}: {STEPS[currentStep - 1].label} - {STEPS[currentStep - 1].description}
                </p>
            </div>
        </div>
    );
};

export default BookingProgress;
