import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Footer() {
  const { isLoggedIn, isOrganizer } = useAuth()
  const cols = [
    {
      title: 'Discover',
      links: [
        { label: 'City Events', to: '/events' },
        { label: 'College Fests', to: '/fests' },
        { label: 'My Passes',     to: '/my-passes' },
        { label: 'Profile',       to: '/profile' },
      ],
    },
    {
      title: 'For Organisers',
      links: [
        ...(isOrganizer
          ? [
              { label: 'Create Event',        to: '/events/create' },
              { label: 'Organiser Dashboard', to: '/organizer' },
            ]
          : [{ label: 'Request Organiser Role', to: '/profile' }]),
      ],
    },
    {
      title: 'Account',
      links: isLoggedIn
        ? [{ label: 'Profile', to: '/profile' }]
        : [
            { label: 'Sign Up', to: '/signup' },
            { label: 'Log In',  to: '/login' },
          ],
    },
  ]

  return (
    <footer className="bg-gray-950 text-gray-400">
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
          {/* Brand */}
          <div>
            <Link to="/" className="flex items-center gap-2.5 mb-5 group">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center">
                <span className="text-white font-bold text-xs">EX</span>
              </div>
              <span className="font-bold text-white text-base">EventX</span>
            </Link>
            <p className="text-sm leading-relaxed text-gray-500">
              Mumbai's premier platform for college fest discovery and registration.
            </p>
          </div>

          {/* Link columns */}
          {cols.map((col) => (
            <div key={col.title}>
              <h4 className="font-semibold text-white mb-5 text-sm tracking-wide">{col.title}</h4>
              <ul className="space-y-3">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link to={link.to} className="text-sm text-gray-500 hover:text-white transition-colors">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-gray-800 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-gray-600">© 2026 EventX. Made with ❤️ in Mumbai.</p>
        </div>
      </div>
    </footer>
  )
}
