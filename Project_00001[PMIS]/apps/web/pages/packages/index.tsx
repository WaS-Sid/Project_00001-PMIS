import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useUser } from "../lib/useUser";
import { getApiClient } from "../lib/api";
import Layout from "../components/Layout";
import styles from "../styles/Packages.module.css";

interface Package {
  id: string;
  code: string;
  title: string;
  data?: Record<string, any>;
}

export default function PackagesPage() {
  const { user } = useUser();
  const [packages, setPackages] = useState<Package[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPackages();
  }, []);

  const fetchPackages = async () => {
    setLoading(true);
    setError(null);
    try {
      const api = getApiClient();
      const data = await api.listPackages();
      setPackages(data);
    } catch (err: any) {
      setError(err.message || "Failed to load packages");
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return (
      <Layout>
        <div className={styles.error}>Please log in first</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className={styles.container}>
        <div className={styles.header}>
          <h1>Packages</h1>
          <p>View and manage procurement packages</p>
        </div>

        {error && <div className={styles.errorBox}>{error}</div>}

        {loading ? (
          <div className={styles.loading}>Loading packages...</div>
        ) : packages.length === 0 ? (
          <div className={styles.empty}>
            <p>No packages found. Create one through the chat interface.</p>
          </div>
        ) : (
          <div className={styles.grid}>
            {packages.map((pkg) => (
              <Link
                key={pkg.id}
                href={`/packages/${pkg.id}`}
                className={styles.card}
              >
                <div className={styles.cardHeader}>
                  <h2>{pkg.code}</h2>
                  <span className={styles.status}>
                    {pkg.data?.status || "pending"}
                  </span>
                </div>
                <p className={styles.title}>{pkg.title}</p>
                <div className={styles.details}>
                  {pkg.data?.total_value && (
                    <div>
                      <strong>Value:</strong> ${pkg.data.total_value}
                    </div>
                  )}
                  {pkg.data?.owner && (
                    <div>
                      <strong>Owner:</strong> {pkg.data.owner}
                    </div>
                  )}
                </div>
                <div className={styles.arrow}>→</div>
              </Link>
            ))}
          </div>
        )}

        <div className={styles.footer}>
          <button onClick={fetchPackages} className={styles.refreshButton}>
            Refresh
          </button>
        </div>
      </div>
    </Layout>
  );
}
