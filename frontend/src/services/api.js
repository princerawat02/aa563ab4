const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getAnalysis(deliveryDate) {
  const response = await fetch(
    `${API_BASE}/api/analysis?delivery_date=${deliveryDate}`,
  );
  if (!response.ok)
    throw new Error(
      (await response.json()).detail || "Unable to load analysis",
    );
  return response.json();
}
