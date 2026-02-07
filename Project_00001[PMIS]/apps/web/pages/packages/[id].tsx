import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import { useUser } from "../../lib/useUser";
import { getApiClient } from "../../lib/api";
import Layout from "../../components/Layout";
import styles from "../../styles/PackageDetail.module.css";

interface Package {
  id: string;
  code: string;
  title: string;
  data?: Record<string, any>;
}

interface AuditEvent {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, any>;
  triggered_by: string;
  created_at: string;
}

export default function PackageDetailPage() {
  const router = useRouter();
  const { id } = router.query;
  const { user } = useUser();
  const [pkg, setPkg] = useState<Package | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id && typeof id === "string") {
      fetchPackageDetail(id);
      fetchAuditTimeline(id);
    }
  }, [id]);

  const fetchPackageDetail = async (packageId: string) => {
    try {
      const api = getApiClient();
      const data = await api.getPackage(packageId);
      setPkg(data);
    } catch (err: any) {
      setError(err.message || "Failed to load package");
    }
  };

  const fetchAuditTimeline = async (packageId: string) => {
    try {
      const api = getApiClient();
      const data = await api.getAuditTimeline("package", packageId, 20);
      setEvents(data);
    } catch (err: any) {
      console.error("Failed to load audit timeline:", err);
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

  if (loading && !pkg) {
    return (
      <Layout>
        <div className={styles.loading}>Loading package details...</div>
      </Layout>
    );
  }

  if (error && !pkg) {
    return (
      <Layout>
        <div className={styles.error}>{error}</div>
      </Layout>
    );
  }

  if (!pkg) {
    return (
      <Layout>
        <div className={styles.error}>Package not found</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className={styles.container}>
        <Link href="/packages" className={styles.backLink}>
          ← Back to Packages
        </Link>

        <div className={styles.header}>
          <div className={styles.titleSection}>
            <h1>{pkg.code}</h1>
            <p>{pkg.title}</p>
          </div>
          <span className={styles.status}>
            {pkg.data?.status || "pending"}
          </span>
        </div>

        <div className={styles.grid}>
          <div className={styles.card}>
            <h2>Details</h2>
            <div className={styles.details}>
              <div className={styles.field}>
                <strong>ID:</strong> <code>{pkg.id}</code>
              </div>
              <div className={styles.field}>
                <strong>Code:</strong> {pkg.code}
              </div>
              <div className={styles.field}>
                <strong>Title:</strong> {pkg.title}
              </div>
              {pkg.data?.owner && (
                <div className={styles.field}>
                  <strong>Owner:</strong> {pkg.data.owner}
                </div>
              )}
              {pkg.data?.total_value && (
                <div className={styles.field}>
                  <strong>Total Value:</strong> ${pkg.data.total_value}
                </div>
              )}
              {pkg.data?.category && (
                <div className={styles.field}>
                  <strong>Category:</strong> {pkg.data.category}
                </div>
              )}
            </div>
          </div>

          <div className={styles.card}>
            <h2>Actions</h2>
            <div className={styles.actions}>
              {user.hasRole("analyst") || user.hasRole("operator") || user.hasRole("admin") ? (
                <>
                  <p>Propose changes to this package via the chat interface.</p>
                  <Link href="/chat" className={styles.actionButton}>
                    Open Chat
                  </Link>
                </>
              ) : (
                <p>You have read-only access to this package.</p>
              )}
            </div>
          </div>
        </div>

        <div className={styles.auditSection}>
          <h2>Audit Timeline</h2>
          {events.length === 0 ? (
            <p className={styles.noEvents}>No events yet</p>
          ) : (
            <div className={styles.timeline}>
              {events.map((event, index) => (
                <div key={event.id} className={styles.timelineEvent}>
                  <div className={styles.timelineDot}></div>
                  <div className={styles.timelineContent}>
                    <div className={styles.eventHeader}>
                      <strong className={styles.eventType}>
                        {event.event_type.replace("_", " ").toUpperCase()}
                      </strong>
                      <span className={styles.eventTime}>
                        {new Date(event.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className={styles.eventTriggered}>
                      by <strong>{event.triggered_by}</strong>
                    </p>
                    {Object.keys(event.payload).length > 0 && (
                      <details className={styles.eventDetails}>
                        <summary>Details</summary>
                        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                      </details>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
