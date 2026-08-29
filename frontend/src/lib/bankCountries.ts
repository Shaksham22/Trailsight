export interface BankCountryVisualizationCentroid {
  bank_country: string;
  iso_alpha2: string;
  centroid_latitude: number;
  centroid_longitude: number;
}

// Frozen bank-country-v1 visualization centroids from the V2 product/data contract.
// These values are deterministic synthetic bank metadata for visualization only;
// they are never customer locations and must not be dynamically geocoded.
export const BANK_COUNTRY_VISUALIZATION_CENTROIDS: readonly BankCountryVisualizationCentroid[] = [
  { bank_country: "Canada", iso_alpha2: "CA", centroid_latitude: 56.1304, centroid_longitude: -106.3468 },
  { bank_country: "United States", iso_alpha2: "US", centroid_latitude: 37.0902, centroid_longitude: -95.7129 },
  { bank_country: "Mexico", iso_alpha2: "MX", centroid_latitude: 23.6345, centroid_longitude: -102.5528 },
  { bank_country: "Brazil", iso_alpha2: "BR", centroid_latitude: -14.235, centroid_longitude: -51.9253 },
  { bank_country: "United Kingdom", iso_alpha2: "GB", centroid_latitude: 55.3781, centroid_longitude: -3.436 },
  { bank_country: "France", iso_alpha2: "FR", centroid_latitude: 46.2276, centroid_longitude: 2.2137 },
  { bank_country: "Germany", iso_alpha2: "DE", centroid_latitude: 51.1657, centroid_longitude: 10.4515 },
  { bank_country: "Netherlands", iso_alpha2: "NL", centroid_latitude: 52.1326, centroid_longitude: 5.2913 },
  { bank_country: "Switzerland", iso_alpha2: "CH", centroid_latitude: 46.8182, centroid_longitude: 8.2275 },
  { bank_country: "Spain", iso_alpha2: "ES", centroid_latitude: 40.4637, centroid_longitude: -3.7492 },
  { bank_country: "United Arab Emirates", iso_alpha2: "AE", centroid_latitude: 23.4241, centroid_longitude: 53.8478 },
  { bank_country: "Saudi Arabia", iso_alpha2: "SA", centroid_latitude: 23.8859, centroid_longitude: 45.0792 },
  { bank_country: "India", iso_alpha2: "IN", centroid_latitude: 20.5937, centroid_longitude: 78.9629 },
  { bank_country: "Pakistan", iso_alpha2: "PK", centroid_latitude: 30.3753, centroid_longitude: 69.3451 },
  { bank_country: "Bangladesh", iso_alpha2: "BD", centroid_latitude: 23.685, centroid_longitude: 90.3563 },
  { bank_country: "Singapore", iso_alpha2: "SG", centroid_latitude: 1.3521, centroid_longitude: 103.8198 },
  { bank_country: "China", iso_alpha2: "CN", centroid_latitude: 35.8617, centroid_longitude: 104.1954 },
  { bank_country: "Japan", iso_alpha2: "JP", centroid_latitude: 36.2048, centroid_longitude: 138.2529 },
  { bank_country: "South Korea", iso_alpha2: "KR", centroid_latitude: 35.9078, centroid_longitude: 127.7669 },
  { bank_country: "Australia", iso_alpha2: "AU", centroid_latitude: -25.2744, centroid_longitude: 133.7751 },
  { bank_country: "South Africa", iso_alpha2: "ZA", centroid_latitude: -30.5595, centroid_longitude: 22.9375 },
  { bank_country: "Nigeria", iso_alpha2: "NG", centroid_latitude: 9.082, centroid_longitude: 8.6753 },
  { bank_country: "Kenya", iso_alpha2: "KE", centroid_latitude: -0.0236, centroid_longitude: 37.9062 },
  { bank_country: "Philippines", iso_alpha2: "PH", centroid_latitude: 12.8797, centroid_longitude: 121.774 },
];

export const BANK_COUNTRY_OPTIONS = BANK_COUNTRY_VISUALIZATION_CENTROIDS.map((country) => country.bank_country);

export function getBankCountryVisualizationCentroid(bankCountry: string): BankCountryVisualizationCentroid | null {
  return BANK_COUNTRY_VISUALIZATION_CENTROIDS.find((country) => country.bank_country === bankCountry) ?? null;
}
