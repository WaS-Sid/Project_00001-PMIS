import React from "react";
import Link from "next/link";
import { useUser, User } from "../lib/useUser";
import styles from "./Layout.module.css";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { user, setUser } = useUser();
  const [showUserMenu, setShowUserMenu] = React.useState(false);

  const handleLogout = () => {
    setUser(null);
  };

  return (
    <div className={styles.container}>
      <nav className={styles.navbar}>
        <div className={styles.navLeft}>
          <Link href="/" className={styles.logo}>
            PMIS
          </Link>
          {user && (
            <div className={styles.navLinks}>
              <Link href="/chat">Chat</Link>
              <Link href="/packages">Packages</Link>
              <Link href="/approvals">Approvals</Link>
            </div>
          )}
        </div>
        <div className={styles.navRight}>
          {user ? (
            <div className={styles.userMenu}>
              <button
                className={styles.userButton}
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                {user.name} ({user.roles.join(", ")})
              </button>
              {showUserMenu && (
                <div className={styles.dropdown}>
                  <button onClick={handleLogout} className={styles.dropdownItem}>
                    Logout
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className={styles.userForm}>
              <p>Demo: Set user to continue</p>
            </div>
          )}
        </div>
      </nav>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
