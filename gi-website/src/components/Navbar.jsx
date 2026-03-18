import { NavLink } from 'react-router-dom'
import { useState } from 'react'
import styles from './Navbar.module.css'

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <nav className={styles.nav}>
      <NavLink to="/" className={styles.logo}>
        Gi Kim
      </NavLink>

      <button
        className={styles.burger}
        onClick={() => setMenuOpen(o => !o)}
        aria-label="Toggle menu"
      >
        <span className={menuOpen ? styles.barTop + ' ' + styles.open : styles.barTop} />
        <span className={menuOpen ? styles.barMid + ' ' + styles.open : styles.barMid} />
        <span className={menuOpen ? styles.barBot + ' ' + styles.open : styles.barBot} />
      </button>

      <ul className={menuOpen ? styles.links + ' ' + styles.mobileOpen : styles.links}>
        {[
          { to: '/', label: 'Home' },
          { to: '/portfolio', label: 'Portfolio' },
          { to: '/resume', label: 'Resume' },
          { to: '/blog', label: 'Blog' },
          { to: '/contact', label: 'Contact' },
        ].map(({ to, label }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                isActive ? styles.link + ' ' + styles.active : styles.link
              }
              onClick={() => setMenuOpen(false)}
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}