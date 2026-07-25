// Kept in exact sync with backend app/schemas.py — if you add/change an
// option or a mandatory field on the backend, mirror it here too.

export const COMPLAINT_SOURCES = [
  "Physician",
  "Pharmacist",
  "Patient",
  "Distributor",
  "Regulatory Body",
  "Sales Rep",
  "Other",
];

export const SITE_BLOCKS = [
  "Block A - Oral Solids",
  "Block B - Sterile/Injectables",
  "Block C - Packaging",
  "Block D - Warehouse/NPM",
  "Block E - R&D Pilot",
];

export const COMPLAINT_CATEGORIES = [
  "Product Quality Defect",
  "Packaging Defect",
  "Adverse Event/Reaction",
  "Counterfeit Suspected",
  "Labeling Error",
  "No Effect/Efficacy Complaint",
  "Foreign Particulate",
  "Other",
];

export const PRIORITY_LEVELS = ["Low", "Medium", "High", "Urgent"];

// Must match MANDATORY_FIELDS in app/schemas.py
export const MANDATORY_FIELDS = [
  "complaint_source",
  "customer_name",
  "product_name",
  "batch_number",
  "originating_site_block",
  "complaint_category",
  "complaint_description",
];

// Human-readable labels, used to build informative chat replies
// (e.g. "Still need: customer name, batch number") instead of a generic line.
export const FIELD_LABELS = {
  complaint_source: "complaint source",
  customer_name: "customer name",
  product_name: "product name",
  product_strength: "product strength/grade",
  batch_number: "batch/lot number",
  affected_quantity: "affected quantity",
  manufacturing_date: "manufacturing date",
  expiry_date: "expiry date",
  originating_site_block: "originating site block",
  impacted_npm: "impacted non-product materials",
  complaint_category: "complaint category",
  complaint_date: "complaint date",
  priority: "priority",
  complaint_description: "complaint description",
};

// Blank shape of extracted_data — every key the backend's
// ExtractedComplaintData schema can populate.
export const EMPTY_EXTRACTED_DATA = {
  complaint_source: "",
  customer_name: "",
  product_name: "",
  product_strength: "",
  batch_number: "",
  affected_quantity: "",
  manufacturing_date: "",
  expiry_date: "",
  originating_site_block: "",
  impacted_npm: "",
  complaint_category: "",
  complaint_date: "",
  priority: "",
  complaint_description: "",
};

export const EMPTY_RISK_ASSESSMENT = {
  severity_suggested: null,
  suggested_next_action: null,
  initial_risk_assessment: null,
};

export function isComplaintComplete(extractedData) {
  return MANDATORY_FIELDS.every((field) => Boolean(extractedData[field]));
}