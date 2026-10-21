import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'

// Pages
import Home              from './pages/Home'
import Login             from './pages/Login'
import Signup            from './pages/Signup'
import Interests         from './pages/Interests'
import CityEventsPage    from './pages/Discover'
import FestsPage         from './pages/Fests/FestsPage'
import EventDetails      from './pages/EventDetails'
import MyPasses          from './pages/MyPasses'
import CreateEvent       from './pages/CreateEvent'
import OrganizerDashboard from './pages/OrganizerDashboard'
import AdminDashboard    from './pages/AdminDashboard'
import Profile           from './pages/Profile'
import FestPage          from './pages/Fests/FestPage'
import FestManage        from './pages/FestManage/FestManage'

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/"           element={<Home />} />
          <Route path="/login"      element={<Login />} />
          <Route path="/signup"     element={<Signup />} />

          {/* Dual-branch routes */}
          <Route path="/fests"      element={<FestsPage />} />
          <Route path="/fest/:slug" element={<FestPage />} />
          <Route path="/events"     element={<CityEventsPage />} />
          <Route path="/events/:id" element={<EventDetails />} />

          {/* Backward-compat redirect */}
          <Route path="/discover"   element={<Navigate to="/events" replace />} />

          {/* Auth required */}
          <Route path="/interests" element={
            <ProtectedRoute><Interests /></ProtectedRoute>
          } />
          <Route path="/my-passes" element={
            <ProtectedRoute><MyPasses /></ProtectedRoute>
          } />
          <Route path="/profile" element={
            <ProtectedRoute><Profile /></ProtectedRoute>
          } />

          {/* Organiser + Admin */}
          <Route path="/events/create" element={
            <ProtectedRoute requiredRole="organizer"><CreateEvent /></ProtectedRoute>
          } />
          {/* Committee dashboard: any logged-in user (it shows only the fests they belong to) */}
          <Route path="/organizer" element={
            <ProtectedRoute><OrganizerDashboard /></ProtectedRoute>
          } />
          <Route path="/organizer/fest/:slug" element={
            <ProtectedRoute><FestManage /></ProtectedRoute>
          } />

          {/* Admin only */}
          <Route path="/admin" element={
            <ProtectedRoute requiredRole="admin"><AdminDashboard /></ProtectedRoute>
          } />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
