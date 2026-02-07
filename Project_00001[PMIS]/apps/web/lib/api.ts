/**
 * API client for PMIS backend
 * Configurable via environment or component props
 */

const getApiBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    // Client-side: use environment variable or default
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  }
  // Server-side: use environment variable or default
  return process.env.API_URL || "http://localhost:8000";
};

export interface UserHeaders {
  "X-User-Id": string;
  "X-User-Role": string;
  "X-User-Name"?: string;
}

export interface ApiError {
  status: number;
  message: string;
  detail?: string;
}

class ApiClient {
  private baseUrl: string;
  private userHeaders: UserHeaders | null = null;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || getApiBaseUrl();
  }

  setUserHeaders(headers: UserHeaders) {
    this.userHeaders = headers;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (this.userHeaders) {
      headers["X-User-Id"] = this.userHeaders["X-User-Id"];
      headers["X-User-Role"] = this.userHeaders["X-User-Role"];
      if (this.userHeaders["X-User-Name"]) {
        headers["X-User-Name"] = this.userHeaders["X-User-Name"];
      }
    }

    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw {
        status: response.status,
        message: body.detail || response.statusText,
        detail: body.detail,
      } as ApiError;
    }
    return response.json();
  }

  /* Chat endpoint */
  async chat(query: string, impactLevel?: string, uncertaintyLevel?: string) {
    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        query,
        impact_level: impactLevel || "medium",
        uncertainty_level: uncertaintyLevel || "medium",
      }),
    });
    return this.handleResponse<any>(response);
  }

  /* Package endpoints */
  async listPackages() {
    const response = await fetch(`${this.baseUrl}/api/packages`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse<any[]>(response);
  }

  async getPackage(packageId: string) {
    const response = await fetch(`${this.baseUrl}/api/packages/${packageId}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse<any>(response);
  }

  async updatePackage(packageId: string, patch: Record<string, any>) {
    const response = await fetch(`${this.baseUrl}/api/packages/${packageId}`, {
      method: "PATCH",
      headers: this.getHeaders(),
      body: JSON.stringify(patch),
    });
    return this.handleResponse<any>(response);
  }

  /* Approval endpoints */
  async listApprovals(status?: string) {
    const url = new URL(`${this.baseUrl}/api/approvals`);
    if (status) url.searchParams.set("status", status);

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse<any[]>(response);
  }

  async approveRequest(approvalId: string, reason?: string) {
    const response = await fetch(
      `${this.baseUrl}/api/approvals/${approvalId}/approve`,
      {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({ reason_text: reason || "" }),
      }
    );
    return this.handleResponse<any>(response);
  }

  async rejectRequest(approvalId: string, reason?: string) {
    const response = await fetch(
      `${this.baseUrl}/api/approvals/${approvalId}/reject`,
      {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({ reason_text: reason || "" }),
      }
    );
    return this.handleResponse<any>(response);
  }

  /* Audit endpoint */
  async getAuditTimeline(
    entityType: string,
    entityId: string,
    limit?: number
  ) {
    const url = new URL(`${this.baseUrl}/api/audit/${entityType}/${entityId}`);
    if (limit) url.searchParams.set("limit", String(limit));

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse<any[]>(response);
  }
}

// Singleton instance
let apiClient: ApiClient | null = null;

export const getApiClient = (baseUrl?: string): ApiClient => {
  if (!apiClient) {
    apiClient = new ApiClient(baseUrl);
  }
  return apiClient;
};

export default ApiClient;
