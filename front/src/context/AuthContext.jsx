import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { getMe } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]           = useState(null)
  const [token, setToken]         = useState(() => localStorage.getItem('token'))
  const [role, setRole]           = useState(() => localStorage.getItem('role') || null)
  const [interestsSet, setInterestsSet] = useState(false)
  const [loading, setLoading]     = useState(true)

  // On mount, try to fetch current user if we have a token
  useEffect(() => {
    if (!token) { setLoading(false); return }
    getMe()
      .then((res) => {
        setUser(res.data)
        setRole(res.data.role)
        setInterestsSet(res.data.interests_set)
      })
      .catch(() => { clearAuth() })
      .finally(() => setLoading(false))
  }, [token])

  const clearAuthRef = useRef(null)

  const saveAuth = useCallback(({ access_token, role, interests_set }) => {
    localStorage.setItem('token', access_token)
    localStorage.setItem('role', role)
    setToken(access_token)
    setRole(role)
    setInterestsSet(interests_set)
  }, [])

  const clearAuth = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    setToken(null)
    setRole(null)
    setUser(null)
    setInterestsSet(false)
  }, [])

  clearAuthRef.current = clearAuth

  // The API client fires this when the server rejects our token (expired or revoked)
  useEffect(() => {
    const onExpired = () => clearAuthRef.current?.()
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  const value = {
    user,
    token,
    role,
    interestsSet,
    setInterestsSet,
    loading,
    isLoggedIn: !!token,
    isAdmin: role === 'admin',
    isOrganizer: role === 'organizer' || role === 'admin',
    saveAuth,
    logout: clearAuth,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
