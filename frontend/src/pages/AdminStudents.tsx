
import React, { useState } from 'react';
import { AppState, User, Booking } from '../types';
import { Card, Badge, Button, Modal } from '../components/UI';
import { Search, Mail, Phone, FileText, User as UserIcon } from 'lucide-react';

interface AdminStudentsProps {
  state: AppState;
}

export const AdminStudents: React.FC<AdminStudentsProps> = ({ state }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStudent, setSelectedStudent] = useState<User | null>(null);

  // 1. Get Admin's Room
  const myRoom = state.readingRooms.find(r => r.ownerId === state.currentUser?.id);
  
  // 2. Get associated data if room exists
  const myCabins = myRoom ? state.cabins.filter(c => c.readingRoomId === myRoom.id) : [];
  const myCabinIds = new Set(myCabins.map(c => c.id));
  
  // Bookings in this venue
  const venueBookings = state.bookings.filter(b => myCabinIds.has(b.cabinId));
  
  // Unique Student IDs who have booked here
  const studentIds = new Set(venueBookings.map(b => b.userId));
  
  // Student Objects
  const students = state.users.filter(u => studentIds.has(u.id));

  // 3. Filter by Search Term
  const filteredStudents = students.filter(s => 
    s.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    s.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Helper to get active booking for a student in this venue
  const getActiveBooking = (studentId: string) => {
    return venueBookings.find(b => b.userId === studentId && b.status === 'ACTIVE');
  };

  if (!myRoom) {
    return (
       <div className="flex flex-col items-center justify-center h-96 text-center">
          <div className="bg-gray-100 p-4 rounded-full mb-4">
             <UserIcon className="h-8 w-8 text-gray-400" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">No Students Yet</h2>
          <p className="text-gray-500 mt-2">Create a reading room to start accepting students.</p>
       </div>
    );
  }

  return (
     <div className="space-y-6">
        {/* Header & Search */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
           <div>
              <h1 className="text-2xl font-bold text-gray-900">Students</h1>
              <p className="text-gray-500">Manage students enrolled in <span className="font-medium text-indigo-600">{myRoom.name}</span>.</p>
           </div>
           <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input 
                 type="text" 
                 placeholder="Search students..." 
                 className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none transition-all shadow-sm"
                 value={searchTerm}
                 onChange={(e) => setSearchTerm(e.target.value)}
              />
           </div>
        </div>

        {/* Student List */}
        <Card className="overflow-hidden border border-gray-200 shadow-sm">
           <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                 <thead className="bg-gray-50">
                    <tr>
                       <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Student</th>
                       <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden md:table-cell">Contact</th>
                       <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                       <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden sm:table-cell">Seat</th>
                       <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                 </thead>
                 <tbody className="bg-white divide-y divide-gray-200">
                    {filteredStudents.length > 0 ? (
                       filteredStudents.map(student => {
                          const activeBooking = getActiveBooking(student.id);
                          return (
                             <tr key={student.id} className="hover:bg-gray-50 transition-colors">
                                <td className="px-6 py-4 whitespace-nowrap">
                                   <div className="flex items-center">
                                      <img 
                                        className="h-10 w-10 rounded-full border border-gray-200 object-cover" 
                                        src={student.avatarUrl || `https://ui-avatars.com/api/?name=${student.name}`} 
                                        alt="" 
                                      />
                                      <div className="ml-3">
                                         <div className="text-sm font-medium text-gray-900">{student.name}</div>
                                         <div className="text-xs text-gray-500">#{student.id.split('-')[1]}</div>
                                      </div>
                                   </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap hidden md:table-cell">
                                   <div className="text-sm text-gray-600 flex items-center gap-2 mb-1">
                                      <Mail className="w-3 h-3 text-gray-400" /> {student.email}
                                   </div>
                                   {student.phone && (
                                       <div className="text-sm text-gray-500 flex items-center gap-2">
                                          <Phone className="w-3 h-3 text-gray-400" /> {student.phone}
                                       </div>
                                   )}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                   <Badge variant={activeBooking ? 'success' : 'info'}>
                                      {activeBooking ? 'Active' : 'Past Student'}
                                   </Badge>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 hidden sm:table-cell">
                                   {activeBooking ? (
                                      <span className="font-mono font-medium text-gray-900 bg-gray-100 px-2 py-1 rounded">
                                         {activeBooking.cabinNumber}
                                      </span>
                                   ) : (
                                      <span className="text-gray-400">--</span>
                                   )}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                   <Button 
                                      variant="ghost" 
                                      size="sm" 
                                      onClick={() => setSelectedStudent(student)}
                                      className="text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50"
                                   >
                                      History
                                   </Button>
                                </td>
                             </tr>
                          );
                       })
                    ) : (
                       <tr>
                          <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                             <div className="flex flex-col items-center">
                                <Search className="h-8 w-8 text-gray-300 mb-2" />
                                <p>No students found matching "{searchTerm}".</p>
                             </div>
                          </td>
                       </tr>
                    )}
                 </tbody>
              </table>
           </div>
        </Card>

        {/* Student Details Modal */}
        {selectedStudent && (
           <Modal 
              isOpen={!!selectedStudent} 
              onClose={() => setSelectedStudent(null)} 
              title="Student Details"
           >
              <div className="text-center mb-6 pt-2">
                 <img 
                    className="h-20 w-20 rounded-full mx-auto mb-3 border-4 border-white shadow-lg" 
                    src={selectedStudent.avatarUrl || `https://ui-avatars.com/api/?name=${selectedStudent.name}`} 
                    alt="" 
                 />
                 <h3 className="text-xl font-bold text-gray-900">{selectedStudent.name}</h3>
                 <p className="text-gray-500 text-sm">{selectedStudent.email}</p>
                 {selectedStudent.phone && <p className="text-gray-400 text-xs mt-1">{selectedStudent.phone}</p>}
              </div>

              <div className="bg-gray-50 p-4 rounded-xl border border-gray-200">
                 <h4 className="text-sm font-bold text-gray-900 mb-4 flex items-center border-b border-gray-200 pb-2">
                    <FileText className="w-4 h-4 mr-2 text-indigo-500" /> Booking History
                 </h4>
                 <div className="space-y-3 max-h-60 overflow-y-auto pr-1 custom-scrollbar">
                    {venueBookings.filter(b => b.userId === selectedStudent.id).length > 0 ? (
                        venueBookings
                        .filter(b => b.userId === selectedStudent.id)
                        .sort((a, b) => new Date(b.startDate).getTime() - new Date(a.startDate).getTime())
                        .map(booking => (
                           <div key={booking.id} className="bg-white p-3 rounded-lg border border-gray-200 shadow-sm text-sm hover:border-indigo-200 transition-colors">
                              <div className="flex justify-between mb-1">
                                 <span className="font-bold text-gray-800">Cabin {booking.cabinNumber}</span>
                                 <Badge variant={booking.status === 'ACTIVE' ? 'success' : 'warning'}>{booking.status}</Badge>
                              </div>
                              <div className="text-gray-500 text-xs flex justify-between mt-2">
                                 <span>{booking.startDate} — {booking.endDate}</span>
                                 <span className="font-medium text-gray-700">₹{booking.amount}</span>
                              </div>
                           </div>
                        ))
                    ) : (
                        <p className="text-center text-gray-400 text-sm py-4">No booking history available.</p>
                    )}
                 </div>
              </div>
              
              <div className="flex justify-end mt-6 pt-4 border-t border-gray-100">
                  <Button onClick={() => setSelectedStudent(null)}>Close</Button>
              </div>
           </Modal>
        )}
     </div>
  );
};
