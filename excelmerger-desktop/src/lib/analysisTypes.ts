export type ColumnType =
  | "numeric"
  | "categorical"
  | "datetime"
  | "identifier"
  | "text"
  | "boolean"
  | "empty"
  | "mixed";

export type AnalysisRole = "measurement" | "grouping" | "datetime" | "text" | "excluded";

export type ColumnSchema = {
  name: string;
  dtype?: string;
  col_type: ColumnType | string;
  file_count: number;
  count?: number;
  unique_approx?: number;
  cardinality?: number;
  sample_rows?: number;
  rows_applicable?: number;
  missing?: number;
  missing_pct?: number;
  invalid_numeric?: number;
  valid_ratio?: number;
  min?: number | null;
  max?: number | null;
  mean?: number | null;
  median?: number | null;
  std?: number | null;
  grouping_suitable?: boolean;
  usable_for_analysis?: boolean;
  reason_excluded?: string;
  analysis_role?: AnalysisRole | string;
  is_label_candidate?: boolean;
  label_values?: string[];
  label_counts?: number[];
  negative_label?: string | null;
  positive_label?: string | null;
  labels_recognized?: boolean;
};

export type DataQualityIssue = {
  severity: "INFO" | "WARNING" | "ERROR" | string;
  file: string;
  column: string;
  issue: string;
  count: number;
  details: string;
};

export type DatasetProfile = {
  key: string;
  source_folder?: string;
  source_file_count?: number;
  cached?: boolean;
  files_scanned: number;
  valid_files: number;
  failed_files: number;
  failed_file_names: string[];
  rows: number;
  total_rows_est: number;
  total_columns: number;
  type_counts: Record<string, number>;
  missing_pct: number;
  missing_values: number;
  duplicate_rows: number;
  duplicate_pct: number;
  invalid_values: number;
  empty_columns: number;
  mixed_columns: number;
  unnamed_columns: number;
  columns: ColumnSchema[];
  numeric_columns: string[];
  all_numeric_columns: string[];
  grouping_columns: string[];
  datetime_columns: string[];
  identifier_columns: string[];
  label_columns: string[];
  excluded_columns: { name: string; reason: string }[];
  issues: DataQualityIssue[];
  errors: string[];
  insights: string[];
  truncated: boolean;
  total_size?: string;
};

export type Statistics = {
  count: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
  p5: number | null;
  p25: number | null;
  p75: number | null;
  p95: number | null;
  q1: number | null;
  q3: number | null;
  iqr: number | null;
  skew: number | null;
  kurtosis: number | null;
  variance: number | null;
  excluded: number | null;
};

export type SpecLimitResult = {
  enabled: boolean;
  n?: number;
  lsl?: number | null;
  usl?: number | null;
  in_spec?: number;
  out_spec?: number;
  below_lsl?: number;
  above_usl?: number;
  pass_pct?: number;
  fail_pct?: number;
  below_pct?: number;
  above_pct?: number;
};

export type DistributionResult = {
  column: string;
  stats: Statistics;
  hist_counts: number[];
  hist_edges: number[];
  kde: { x: number; d: number }[];
  outlier_count: number;
  outlier_pct: number;
  bounds: { lower: number | null; upper: number | null };
  excluded_values: number;
  missing_values: number;
  files_with_column: number;
  files_total: number;
  spec: SpecLimitResult;
  preview: Record<string, unknown>[];
  insights: string[];
};

export type GroupStatistics = {
  group: string;
  count: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
  p5: number | null;
  p25: number | null;
  p75: number | null;
  p95: number | null;
  iqr: number | null;
  outlier_count: number;
};

export type ComparisonResult = {
  value_col: string;
  group_by: string;
  groups: GroupStatistics[];
  total_groups: number;
  truncated: boolean;
  bucketed?: boolean;
  overall?: Omit<GroupStatistics, "group">;
  insights: string[];
};

export type CorrelationResult = {
  columns: string[];
  matrix: Array<Array<number | null>>;
  pairs: { x: string; y: string; r: number; n: number }[];
  method: string;
  excluded: { name: string; reason: string }[];
  insights?: string[];
  message?: string;
};

export type ScatterResult = {
  x: string;
  y: string;
  group_by?: string;
  n: number;
  r: number | null;
  r2: number | null;
  slope: number | null;
  intercept: number | null;
  fit?: { x: number; y: number }[];
  points: { x: number; y: number; o?: boolean }[];
  series: { name: string; points: { x: number; y: number }[] }[];
  total_points: number;
  sampled: boolean;
  outlier_count: number;
  insights: string[];
};

export type TrendResult = {
  time_col: string;
  value_col: string;
  aggregation: string;
  n: number;
  points: { t: string; v: number; roll: number; outlier: boolean }[];
  stats?: Statistics;
  outlier_count?: number;
  sampled?: boolean;
  total_points?: number;
  range?: { from: string; to: string };
  insights: string[];
};

export type BatchStatistics = Omit<GroupStatistics, "group"> & {
  batch: string;
  pass_rate: number | null;
  in_spec_pct: number | null;
};

export type BatchResult = {
  value_col: string;
  unit: string;
  label_col?: string;
  positive_label?: string;
  batches: BatchStatistics[];
  total_batches: number;
  truncated: boolean;
  insights: string[];
};

export type TablePage = {
  columns: string[];
  rows: Record<string, string | number | null>[];
  total: number;
  offset: number;
  limit: number;
  numeric_columns: string[];
};

export type ThresholdRow = {
  threshold: number;
  lower: number | null;
  upper: number | null;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number;
  recall: number;
  specificity: number;
  f1: number;
  accuracy: number;
  false_accept_rate: number;
  false_reject_rate: number;
  false_accept_rate_ng: number;
  false_reject_rate_ok: number;
  yield: number;
  youden: number;
  cost: number;
};

export type StatisticalLimitResult = {
  method: string;
  basis?: string;
  limit_type: string;
  lower: number | null;
  upper: number | null;
  n: number;
  below_lower?: number;
  above_upper?: number;
  out_of_limits?: number;
  out_of_limits_pct?: number;
  stats?: Statistics;
  warnings: string[];
};

export type LimitResult = {
  mode: "supervised" | "statistical";
  supervised: boolean;
  measurement: string;
  label_col?: string;
  negative_label?: string;
  positive_label?: string;
  limit_type: "upper" | "lower" | "two_sided" | string;
  optimization_method: string;
  method?: string;
  costs?: { false_accept: number; false_reject: number };
  class_counts?: Record<string, number>;
  n?: number;
  recommended?: ThresholdRow;
  recommended_lower: number | null;
  recommended_upper: number | null;
  current?: ThresholdRow | null;
  thresholds?: ThresholdRow[];
  roc?: { fpr: number; tpr: number; threshold: number }[];
  auc?: number | null;
  boundary?: {
    edges: number[];
    ok: number[];
    ng: number[];
    ok_density?: number[];
    ng_density?: number[];
    overlap_pct: number | null;
  };
  statistical?: StatisticalLimitResult;
  value_range?: { min: number | null; max: number | null };
  warnings: string[];
  insights: string[];
};

export type ThresholdEvaluation = {
  lower: number | null;
  upper: number | null;
  limit_type: string;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  rejected: number;
  missed_defects: number;
  precision: number;
  recall: number;
  specificity: number;
  f1: number;
  accuracy: number;
  false_accept_rate: number;
  false_reject_rate: number;
  yield: number;
  youden: number;
  cost: number;
  warnings: string[];
};

export type AnalysisPreset = {
  name: string;
  type: string;
  savedAt: string;
  config: Record<string, unknown>;
};
