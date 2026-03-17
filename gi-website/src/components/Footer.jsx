import styles from './Footer.module.css'

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <p className={styles.text}>
        © {new Date().getFullYear()} Gi Kim &mdash; Built with React &amp; hosted on Google Cloud
      </p>
    </footer>
  )
}
