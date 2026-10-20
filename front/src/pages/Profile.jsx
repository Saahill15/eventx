import { useState } from 'react'
import { errorMessage } from '../lib/errors'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { requestOrganizer } from '../services/api'
import { useAuth } from '../context/AuthContext'

const ROLE_BADGE = {
  user:      'bg-gray-100 text-gray-600',
  organizer: 'bg-violet-100 text-violet-700',
  admin:     'bg-rose-100 text-rose-700',
}

export default function Profile() {
  const { user, role, logout } = useAuth()
  const navigate = useNavigate()
  const [reqLoading, setReqLoading] = useState(false)
  const [reqMsg, setReqMsg]         = useState('')

  const handleLogout = () => { logout(); navigate('/') }

  const handleRequestOrganizer = async () => {
    setReqLoading(true)
    setReqMsg('')
    try {
      const r = await requestOrganizer()
      setReqMsg(r.data.message)
    } catch (err) {
      setReqMsg(errorMessage(err, 'Failed to submit request.'))
    } finally {
      setReqLoading(false)
    }
  }

  const joinedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
    : ''

  return (
    <div className="min-h-screen bg-[#fafaf9]">
      <Navbar />
      <div className="max-w-2xl mx-auto px-6 pt-28 pb-20">
        {/* Avatar + name */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex flex-col items-center text-center mb-10"
        >
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center shadow-lg mb-5">
            <span className="text-white font-bold text-3xl">
              {user?.name?.charAt(0)?.toUpperCase() ?? '?'}
            </span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{user?.name}</h1>
          <p className="text-gray-500 text-sm mt-1">{user?.email}</p>
          <div className="flex items-center gap-2 mt-3">
            <span className={`text-xs font-semibold px-3 py-1.5 rounded-full capitalize ${ROLE_BADGE[role] ?? ROLE_BADGE.user}`}>
              {role}
            </span>
            {joinedDate && (
              <span className="text-xs text-gray-400">Joined {joinedDate}</span>
            )}
          </div>
        </motion.div>

        {/* Quick actions */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          {[
            { label: '🎫 My Passes', to: '/my-passes' },
            { label: '🔍 Discover', to: '/discover' },
            ...(role === 'organizer' || role === 'admin'
              ? [
                  { label: '🎪 My Events', to: '/organizer' },
                  { label: '➕ Create Event', to: '/events/create' },
                ]
              : []),
            ...(role === 'admin' ? [{ label: '🛡 Admin Panel', to: '/admin' }] : []),
          ].map((item) => (
            <Link
              key={item.label}
              to={item.to}
              className="bg-white rounded-2xl p-4 text-sm font-semibold text-gray-700 hover:text-orange-600 hover:shadow-md transition-all shadow-sm text-center"
            >
              {item.label}
            </Link>
          ))}
        </div>

        {/* Organiser request (only for regular users) */}
        {role === 'user' && (
          <div className="bg-white rounded-2xl p-6 mb-6 shadow-sm">
            <h3 className="font-bold text-gray-900 mb-2">Become an Organiser</h3>
            <p className="text-sm text-gray-500 mb-4">
              Want to host events on EventX? Request organiser access and start creating events.
            </p>
            {reqMsg ? (
              <p className="text-sm font-medium text-green-600">{reqMsg}</p>
            ) : (
              <button
                onClick={handleRequestOrganizer}
                disabled={reqLoading}
                className="bg-gray-900 text-white text-sm font-semibold px-5 py-2.5 rounded-full hover:bg-gray-700 transition-all active:scale-95 disabled:opacity-60"
              >
                {reqLoading ? 'Submitting…' : 'Request Organiser Role'}
              </button>
            )}
          </div>
        )}

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-full py-3.5 rounded-2xl border-2 border-red-100 text-red-500 font-semibold text-sm hover:bg-red-50 transition-colors"
        >
          Logout
        </button>
      </div>
      <Footer />
    </div>
  )
}
