import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Navbar() {
  const [scrolled, setScrolled]   = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { isLoggedIn, isAdmin, isOrganizer, logout, user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/')
    setMobileOpen(false)
  }

  const navLinks = [
    { label: 'Home',          to: '/' },
    { label: 'College Fests', to: '/fests' },
    { label: 'City Events',   to: '/events' },
    ...(isLoggedIn ? [{ label: 'My Passes', to: '/my-passes' }] : []),
    ...(isLoggedIn ? [{ label: 'Committee', to: '/organizer' }] : []),
    ...(isAdmin ? [{ label: 'Admin', to: '/admin' }] : []),
  ]

  return (
    <motion.nav
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-white/85 backdrop-blur-xl border-b border-gray-100 shadow-[0_1px_20px_rgba(0,0,0,0.06)]'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center shadow-lg shadow-orange-200 group-hover:scale-105 transition-transform">
            <span className="text-white font-bold text-xs tracking-tight">EX</span>
          </div>
          <span className="font-bold text-gray-900 text-[1.05rem] tracking-tight">EventX</span>
        </Link>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => (
            <Link
              key={link.label}
              to={link.to}
              className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-900 rounded-xl hover:bg-gray-50 transition-all"
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Auth CTAs */}
        <div className="hidden md:flex items-center gap-3">
          {isLoggedIn ? (
            <>
              <Link to="/profile" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors px-3 py-1.5">
                {user?.name?.split(' ')[0] ?? 'Profile'}
              </Link>
              <button
                onClick={handleLogout}
                className="text-sm font-semibold bg-gray-900 text-white px-5 py-2.5 rounded-full hover:bg-gray-700 transition-all hover:shadow-lg hover:shadow-gray-200 active:scale-95"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors px-3 py-1.5">
                Sign in
              </Link>
              <Link
                to="/signup"
                className="text-sm font-semibold bg-gray-900 text-white px-5 py-2.5 rounded-full hover:bg-gray-700 transition-all hover:shadow-lg hover:shadow-gray-200 active:scale-95"
              >
                Get Started
              </Link>
            </>
          )}
        </div>

        {/* Mobile toggle */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden w-10 h-10 flex flex-col items-center justify-center gap-1.5 rounded-xl hover:bg-gray-50 transition-colors"
          aria-label="Menu"
        >
          <motion.span animate={mobileOpen ? { rotate: 45, y: 6 } : { rotate: 0, y: 0 }} className="block w-5 h-0.5 bg-gray-800 rounded-full origin-center" />
          <motion.span animate={mobileOpen ? { opacity: 0, x: -6 } : { opacity: 1, x: 0 }} className="block w-5 h-0.5 bg-gray-800 rounded-full" />
          <motion.span animate={mobileOpen ? { rotate: -45, y: -6 } : { rotate: 0, y: 0 }} className="block w-5 h-0.5 bg-gray-800 rounded-full origin-center" />
        </button>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden bg-white/95 backdrop-blur-xl border-t border-gray-100 overflow-hidden"
          >
            <div className="px-6 py-4 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.label}
                  to={link.to}
                  onClick={() => setMobileOpen(false)}
                  className="block px-4 py-3 text-sm font-medium text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
                >
                  {link.label}
                </Link>
              ))}
              <div className="flex gap-3 pt-3 border-t border-gray-100 mt-2">
                {isLoggedIn ? (
                  <button onClick={handleLogout} className="flex-1 text-center py-2.5 text-sm font-semibold bg-gray-900 text-white rounded-full">
                    Logout
                  </button>
                ) : (
                  <>
                    <Link to="/login" onClick={() => setMobileOpen(false)} className="flex-1 text-center py-2.5 text-sm font-medium text-gray-700 border border-gray-200 rounded-full">
                      Sign in
                    </Link>
                    <Link to="/signup" onClick={() => setMobileOpen(false)} className="flex-1 text-center py-2.5 text-sm font-semibold bg-gray-900 text-white rounded-full">
                      Get Started
                    </Link>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  )
}
