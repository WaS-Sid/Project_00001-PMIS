import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useUser } from "../lib/useUser";
import { getApiClient } from "../lib/api";
import Layout from "../components/Layout";
import styles from "../styles/Approvals.module.css";

interface Approval {
  id: string;
  package_id: string;
  patch_json: Record<string, any>;
  status: string;
  requested_by: string;
  created_at: string;
}

export default function ApprovalsPage() {
  const { user, hasRole } = useUser();
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchApprovals();
  }, []);

  const fetchApprovals = async () => {
    setLoading(true);
    setError(null);
    try {
      const api = getApiClient();
      const data = await api.listApprovals();
      setApprovals(data);
    } catch (err: any) {
      setError(err.message || "Failed to load approvals");
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (approvalId: string) => {
    setActionInProgress(approvalId);
    try {
      const api = getApiClient();
      await api.approveRequest(approvalId, "Approved via UI");
      // Refresh list
      await fetchApprovals();
    } catch (err: any) {
      setError(err.message || "Failed to approve");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleReject = async (approvalId: string) => {
    setActionInProgress(approvalId);
    try {
      const api = getApiClient();
      await api.rejectRequest(
        approvalId,
        rejectReason[approvalId] || "Rejected via UI"
      );
      // Refresh list
      await fetchApprovals();
      setRejectReason((prev) => {
        const next = { ...prev };
        delete next[approvalId];
        return next;
      });
    } catch (err: any) {
      setError(err.message || "Failed to reject");
    } finally {
      setActionInProgress(null);
    }
  };

  if (!user) {
    return (
      <Layout>
        <div className={styles.error}>Please log in first</div>
      </Layout>
    );
  }

  const canApprove = hasRole("admin");
  const pendingApprovals = approvals.filter((a) => a.status === "pending");

  return (
    <Layout>
      <div className={styles.container}>
        <div className={styles.header}>
          <h1>Approvals</h1>
          <p>{pendingApprovals.length} pending approval(s)</p>
        </div>

        {error && (
          <div className={styles.errorBox}>
            {error}
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}

        {!canApprove && (
          <div className={styles.infoBox}>
                Only admins can approve/reject requests. You have read-only access.
          </div>
        )}

        {loading ? (
          <div className={styles.loading}>Loading approvals...</div>
        ) : approvals.length === 0 ? (
          <div className={styles.empty}>
            <p>No approval requests yet.</p>
          </div>
        ) : (
          <div className={styles.approvalsList}>
            {approvals.map((approval) => (
              <div
                key={approval.id}
                className={`${styles.approvalCard} ${styles[approval.status]}`}
              >
                <div className={styles.cardHeader}>
                  <div>
                    <h3>Package: {approval.package_id}</h3>
                    <p className={styles.requestedBy}>
                      Requested by: <strong>{approval.requested_by}</strong>
                    </p>
                  </div>
                  <span className={`${styles.badge} ${styles[approval.status]}`}>
                    {approval.status.toUpperCase()}
                  </span>
                </div>

                <div className={styles.patchSection}>
                  <h4>Proposed Changes:</h4>
                  <div className={styles.patchContent}>
                    {Object.entries(approval.patch_json).map(([key, value]) => (
                      <div key={key} className={styles.patchItem}>
                        <code>{key}</code>
                        <span> → </span>
                        <code>{JSON.stringify(value)}</code>
                      </div>
                    ))}
                  </div>
                </div>

                <div className={styles.createdAt}>
                  Created: {new Date(approval.created_at).toLocaleString()}
                </div>

                {approval.status === "pending" && canApprove && (
                  <div className={styles.actions}>
                    <button
                      className={styles.approveButton}
                      onClick={() => handleApprove(approval.id)}
                      disabled={actionInProgress === approval.id}
                    >
                      {actionInProgress === approval.id ? "..." : "✓ Approve"}
                    </button>
                    <div className={styles.rejectGroup}>
                      <textarea
                        className={styles.rejectReason}
                        placeholder="Optional rejection reason"
                        value={rejectReason[approval.id] || ""}
                        onChange={(e) =>
                          setRejectReason((prev) => ({
                            ...prev,
                            [approval.id]: e.target.value,
                          }))
                        }
                      />
                      <button
                        className={styles.rejectButton}
                        onClick={() => handleReject(approval.id)}
                        disabled={actionInProgress === approval.id}
                      >
                        {actionInProgress === approval.id
                          ? "..."
                          : "✕ Reject"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className={styles.tabSelector}>
          <button
            className={`${styles.tab} ${
              approvals.length > 0 ? styles.active : ""
            }`}
            onClick={() => {}}
          >
            All ({approvals.length})
          </button>
          <button className={styles.tab}>
            Pending ({pendingApprovals.length})
          </button>
          <button className={styles.tab}>
            Approved ({approvals.filter((a) => a.status === "approved").length})
          </button>
          <button className={styles.tab}>
            Rejected ({approvals.filter((a) => a.status === "rejected").length})
          </button>
        </div>
      </div>
    </Layout>
  );
}
